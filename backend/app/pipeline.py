"""Glue: Ring -> clip -> OpenCV -> AI assessment -> DB."""
import os, random, threading, time
from pathlib import Path

import cv2
import numpy as np

try:
    import boto3
except ImportError:
    boto3 = None

from . import db
from .assess import assess
from .frames import FileSource
from .ring import ring, MediaNotReady, RingError
from .vision import analyze

CLIPS = Path("clips")
CLIPS.mkdir(exist_ok=True)
_lock = threading.Lock()  # one Ring sync at a time

CLIPS_BACKEND = os.getenv("CLIPS_BACKEND", "local")
S3_BUCKET = os.getenv("S3_BUCKET", "")


def _upload_clip_to_s3(local_path: Path) -> bool:
    """Upload clip to S3 and delete local file. Returns True on success. Never raises."""
    if not boto3 or not S3_BUCKET:
        return False
    try:
        region = os.getenv("S3_REGION", os.getenv("AWS_REGION", "ap-south-1"))
        s3 = boto3.client("s3", region_name=region)
        key = f"clips/{local_path.name}"
        s3.upload_file(str(local_path), S3_BUCKET, key)
        local_path.unlink(missing_ok=True)
        return True
    except Exception as exc:
        import logging
        logging.getLogger("ringcare.pipeline").warning(
            f"[s3] Failed to upload {local_path.name}: {exc}"
        )
        return False


# ---------- local sample clips (so the app works before you add real footage) ----------
def _room(w=640, h=360):
    img = np.zeros((h, w, 3), np.uint8)
    img[:] = (150, 160, 170)
    img[int(h * 0.7):] = (90, 100, 110)  # floor
    return img


def _write(stem, draw, n=60, fps=15, size=(640, 360)):
    """Write a browser-playable clip. OpenCV usually can't encode H.264, and MPEG-4 Part 2 ('mp4v')
    won't play in browsers, so prefer WebM/VP8 and only fall back to mp4v (analysis still works)."""
    for ext, code in (("webm", "VP80"), ("mp4", "mp4v")):
        path = CLIPS / f"{stem}.{ext}"
        vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*code), fps, size)
        if not vw.isOpened():
            continue
        for i in range(n):
            vw.write(draw(i))
        vw.release()
        return path


def ensure_sample_clips():
    """Synthetic placeholders. Replace/add real clips (walking, sitting, lying...) in backend/clips/."""
    if sample_clips():
        return

    def walk(i):
        f = _room(); x = 80 + i * 7
        cv2.rectangle(f, (x, 120), (x + 50, 270), (60, 60, 160), -1)
        cv2.circle(f, (x + 25, 100), 22, (170, 200, 230), -1)
        return f

    def still(i):
        f = _room()
        noise = np.random.randint(0, 3, f.shape, dtype=np.uint8)
        return cv2.add(f, noise)

    _write("sample_walk", walk)
    _write("sample_empty", still)


def make_playable(path: Path) -> Path:
    """Browsers can't play every codec Ring/OpenCV produce (HEVC, MPEG-4 Part 2...).
    Re-encode to WebM/VP8 with OpenCV (already a dependency) so the dashboard player always works.
    Falls back to the original file if re-encoding isn't possible."""
    if path.suffix == ".webm":
        return path
    out = path.with_name(path.stem + ".play.webm")
    if out.exists():
        return out
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return path
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    scale = min(1.0, 960 / w) if w else 1.0
    size = (max(2, int(w * scale) // 2 * 2), max(2, int(h * scale) // 2 * 2))
    vw = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"VP80"), fps, size)
    if not vw.isOpened():
        cap.release()
        return path
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        vw.write(cv2.resize(frame, size) if scale < 1.0 else frame)
        n += 1
    vw.release()
    cap.release()
    if n == 0:
        out.unlink(missing_ok=True)
        return path
    return out


def sample_clips():
    return sorted(p for ext in ("*.mp4", "*.webm", "*.mov") for p in CLIPS.glob(ext)
                  if not p.name.startswith("ring_") and ".play." not in p.name)


# ---------- processing ----------
def process_clip(path: Path, meta: dict):
    vision = analyze(FileSource(str(path)))
    result = assess(meta, vision)
    thumb = (vision.get("keyframes") or [None])[0]
    return vision, result, thumb


def simulate(video: str | None = None, device_id="local-sample", device_name="Local sample camera") -> int:
    if video:
        path = CLIPS / Path(video).name  # no path traversal
        if not path.exists():
            raise FileNotFoundError(f"No clip named {path.name} in backend/clips/")
    else:
        opts = sample_clips()
        if not opts:
            raise FileNotFoundError("No clips found in backend/clips/")
        path = random.choice(opts)
    meta = {"device_id": device_id, "source": "simulated", "clip": path.name}
    try:
        vision, result, thumb = process_clip(path, meta)
        clip_playable = make_playable(path)
        clip_file = clip_playable.name
        if CLIPS_BACKEND == "s3" and S3_BUCKET:
            uploaded = _upload_clip_to_s3(clip_playable)
            if not uploaded:
                # Upload failed; local file still exists but won't survive container restart.
                # Surface this honestly so the clip route doesn't serve a broken pre-signed URL.
                clip_file = None
                video_status = "unavailable"
            else:
                video_status = "sample"
        else:
            video_status = "sample"
    except Exception as exc:
        vision = {"error": f"Clip analysis failed: {exc}"}
        result = assess(meta, vision)
        thumb = None
        clip_file = None
        video_status = "unavailable"

    return db.insert(device_id, device_name, "simulated", vision, result, thumb,
                     clip_file=clip_file, video_status=video_status)


def _ingest_device(dev: dict, limit: int, wait: int, notes: list) -> list:
    allow_fallback = os.getenv("RING_SAMPLE_FALLBACK", "true").lower() == "true"
    try:
        events = ring.events(dev["id"], limit=25)
    except RingError as e:
        notes.append(f"{dev['name']}: event history failed ({e.message[:120]})")
        return []
    fresh = [e for e in events if not db.has_ring_event(e["id"])][:limit]
    ids = []
    for e in reversed(fresh):  # oldest first
        start = e["start_ms"] or int(time.time() * 1000)
        meta = {"device_id": dev["id"], "device_name": dev["name"], "ring_event_type": e["event_type"],
                "ring_sub_type": e["sub_type"], "source": "ring"}
        path, source = CLIPS / f"ring_{dev['id'][-8:]}_{e['id'][-12:]}.mp4".replace(":", "_"), "ring"
        try:
            data = ring.clip(dev["id"], max(0, start - 2000), 10000, retry_seconds=wait)
            path.write_bytes(data)
        except MediaNotReady as err:
            notes.append(f"{dev['name']}: no clip for event {e['id'][-8:]} ({err.status}).")
            path = None
        except RingError as err:
            notes.append(f"{dev['name']}: clip download failed ({err.status}: {err.message[:100]}).")
            path = None
        if path is None:
            samples = sample_clips() if allow_fallback else []
            if samples:
                path, source = random.choice(samples), "ring+sample-clip"
            else:
                vision = {"error": "Ring clip unavailable and sample fallback disabled"}
                rid = db.insert(dev["id"], dev["name"], "ring", vision, assess(meta, vision), None,
                                event_ts=start / 1000, ring_event_id=e["id"], video_status="unavailable")
                if rid:
                    ids.append(rid)
                continue

        try:
            vision, result, thumb = process_clip(path, meta)
            clip_playable = make_playable(path)
            v_status = "sample" if source == "ring+sample-clip" else (
                "converted" if ".play." in clip_playable.name or clip_playable.suffix == ".webm" else "ring_clip"
            )
            clip_name = clip_playable.name
            if CLIPS_BACKEND == "s3" and S3_BUCKET:
                uploaded = _upload_clip_to_s3(clip_playable)
                if not uploaded:
                    # Upload failed: clear clip_name so the clip route returns 404
                    # rather than a pre-signed URL for a key that doesn't exist in S3.
                    clip_name = None
                    v_status = "unavailable"
        except Exception as exc:
            notes.append(f"{dev['name']}: clip analysis failed ({exc}).")
            vision = {"error": f"Clip analysis failed: {exc}"}
            result = assess(meta, vision)
            thumb = None
            clip_name = None
            v_status = "unavailable"

        rid = db.insert(dev["id"], dev["name"], source, vision, result, thumb, event_ts=start / 1000,
                        ring_event_id=e["id"], clip_file=clip_name, video_status=v_status)
        if rid:
            ids.append(rid)
    return ids


def sync_ring(limit=5, wait=0, only_device: str | None = None) -> dict:
    """Pull new events + clips from Ring. Returns {'ids': [...], 'notes': [...]}."""
    if not ring.configured:
        raise RingError(400, "Ring is not configured. Set RING_ACCESS_TOKEN (Playground) in backend/.env")
    notes, ids = [], []
    with _lock:
        devices = ring.devices()
        if only_device:
            devices = [d for d in devices if d["id"] == only_device] or [{"id": only_device, "name": "Ring device"}]
        for d in devices:
            ids += _ingest_device(d, limit, wait, notes)
    return {"ids": ids, "notes": notes}
