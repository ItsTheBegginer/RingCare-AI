"""Vision analysis: motion gating + keyframe extraction + Amazon Rekognition person/signal detection,
with robust OpenCV HOG fallback.
"""
import base64
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .frames import FrameSource

logger = logging.getLogger("ringcare.vision")

_hog = None
_hog_error = None
WARMUP = 3

# Signal labels to capture from AWS Rekognition DetectLabels (v3.0)
CARETAKING_SIGNALS = {
    "Fallen Person", "Injury", "Crawling", "Kneeling",
    "Sitting", "Standing", "Walking", "Sleeping",
    "Floor", "Flooring", "Ground", "Bed", "Couch", "Bedroom"
}

SECURITY_SIGNALS = {
    "Weapon", "Gun", "Handgun", "Firearm", "Knife", "Dagger", "Blade",
    "Mask", "Gas Mask",
    "Fighting", "Window - Broken", "Fire", "Smoke"
}

ALL_SIGNAL_LABELS = CARETAKING_SIGNALS | SECURITY_SIGNALS

# In-memory daily spend cap tracker: (YYYY-MM-DD, count)
_daily_cap_tracker = {"date": "", "count": 0}


def _get_hog():
    """Create the HOG person detector lazily so a broken OpenCV build can't stop the server starting."""
    global _hog, _hog_error
    if _hog is None and _hog_error is None:
        try:
            h = cv2.HOGDescriptor()
            h.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            _hog = h
        except Exception as e:
            _hog_error = f"{type(e).__name__}: {e}"
            logger.warning(f"Person detector unavailable ({_hog_error}); using motion analysis only.")
    return _hog


def _jpeg_b64(frame, width=640):
    h, w = frame.shape[:2]
    frame = cv2.resize(frame, (width, int(h * width / w)))
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return base64.b64encode(buf).decode()


def _check_and_increment_daily_cap(increment: int) -> bool:
    """Returns True if within spend cap, False if cap exceeded."""
    cap = int(os.getenv("REKOGNITION_DAILY_CAP", "300"))
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if _daily_cap_tracker["date"] != today:
        _daily_cap_tracker["date"] = today
        _daily_cap_tracker["count"] = 0
    if _daily_cap_tracker["count"] + increment > cap:
        return False
    _daily_cap_tracker["count"] += increment
    return True


def _analyze_opencv(scored_samples, duration, n_keyframes=4, detector_label="hog"):
    """Original OpenCV HOG pipeline used as primary or fallback detector."""
    hog = _get_hog()
    person_hits = 0
    wide_hits = 0
    best_person = None
    ratios = [s[0] for s in scored_samples]

    for ratio, small in scored_samples:
        if ratio > 0.01 and hog is not None:
            rects, weights = hog.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)
            if len(rects):
                person_hits += 1
                i = int(np.argmax([w * h for (_, _, w, h) in rects]))
                x, y, w, h = [int(v) for v in rects[i]]
                if w / h > 1.0:
                    wide_hits += 1
                try:
                    conf = float(np.clip(np.ravel(weights)[i] / 2.0, 0.05, 0.99))
                except Exception:
                    conf = 0.5
                if best_person is None or ratio > best_person[0]:
                    best_person = (ratio, small, (x, y, w, h), conf)

    frames = [f for _, f in sorted(scored_samples, key=lambda t: -t[0])[:n_keyframes]]
    bbox = None
    if best_person:
        _, pf, (x, y, w, h), conf = best_person
        H, W = pf.shape[:2]
        pct = lambda v, t: round(float(np.clip(100 * v / t, 0, 100)), 1)
        bbox = {
            "top": pct(y, H),
            "left": pct(x, W),
            "width": pct(w, W),
            "height": pct(h, H),
            "confidence": round(conf, 2),
        }
        frames = [pf] + [f for f in frames if f is not pf][: n_keyframes - 1]

    arr = np.array(ratios) if ratios else np.array([0.0])
    return {
        "frames_sampled": len(scored_samples),
        "duration_s": round(duration, 1),
        "motion_avg": round(float(arr.mean()), 4),
        "motion_peak": round(float(arr.max()), 4),
        "motion_frames_pct": round(100 * float((arr > 0.01).mean()), 1),
        "person_detected": person_hits > 0,
        "person_frames_pct": round(100 * person_hits / max(1, len(ratios)), 1),
        "wide_posture_frames_pct": round(100 * wide_hits / max(1, len(ratios)), 1),
        "bbox": bbox,
        "keyframes": [_jpeg_b64(f) for f in frames],
        "detector": detector_label,
        "per_frame": [],
    }


def _analyze_rekognition(scored_samples, duration, n_keyframes=4, rekognition_client=None):
    """Amazon Rekognition DetectLabels pipeline on evenly spaced keyframes + peak motion frame."""
    import boto3

    client = rekognition_client or boto3.client(
        "rekognition",
        region_name=os.getenv("AWS_REGION", "ap-south-1")
    )
    max_frames = int(os.getenv("REKOGNITION_MAX_FRAMES", "6"))
    min_confidence = float(os.getenv("REKOGNITION_MIN_CONFIDENCE", "50"))

    # Select frames: evenly spread across clip + peak motion frame
    n_samples = len(scored_samples)
    if n_samples <= max_frames:
        selected_indices = list(range(n_samples))
    else:
        step = n_samples / max_frames
        selected_indices = [int(i * step) for i in range(max_frames)]
        # Ensure the peak motion frame is included
        peak_idx = int(np.argmax([s[0] for s in scored_samples]))
        if peak_idx not in selected_indices:
            selected_indices[-1] = peak_idx
        selected_indices = sorted(set(selected_indices))

    # Check daily spend cap
    if not _check_and_increment_daily_cap(len(selected_indices)):
        logger.warning("Rekognition daily cap exceeded; falling back to OpenCV HOG detector.")
        return _analyze_opencv(scored_samples, duration, n_keyframes=n_keyframes, detector_label="hog (rekognition daily cap exceeded)")

    per_frame_results = []
    person_frames_count = 0
    wide_posture_count = 0
    best_person = None  # (confidence, frame, bbox_dict)

    for idx in selected_indices:
        ratio, frame = scored_samples[idx]
        frame_t = round((idx / max(1, n_samples - 1)) * duration, 2)

        # Resize to <= 960px wide for Rekognition
        h, w = frame.shape[:2]
        target_w = min(w, 960)
        target_h = int(h * target_w / w)
        resized = cv2.resize(frame, (target_w, target_h))
        ok, buf = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            continue
        jpeg_bytes = buf.tobytes()

        # Call Rekognition DetectLabels
        resp = client.detect_labels(
            Image={"Bytes": jpeg_bytes},
            MaxLabels=40,
            MinConfidence=min_confidence,
        )

        labels = resp.get("Labels", [])
        matched_signals = []
        has_person = False
        person_conf = 0.0
        frame_bbox = None
        is_wide = False

        for lbl in labels:
            name = lbl["Name"]
            conf = float(lbl["Confidence"])

            if name in ALL_SIGNAL_LABELS:
                matched_signals.append({"label": name, "confidence": round(conf, 1)})

            if name == "Person":
                has_person = True
                person_conf = max(person_conf, conf)
                instances = lbl.get("Instances", [])
                if instances:
                    # Pick instance with highest confidence or largest box
                    inst = max(instances, key=lambda i: i.get("Confidence", 0))
                    box = inst.get("BoundingBox", {})
                    bw = float(box.get("Width", 0))
                    bh = float(box.get("Height", 0))
                    bl = float(box.get("Left", 0))
                    bt = float(box.get("Top", 0))
                    # Check wide posture: (width * img_w) / (height * img_h) > 1.0
                    if bh > 0 and (bw * target_w) / (bh * target_h) > 1.0:
                        is_wide = True

                    frame_bbox = {
                        "top": round(bt * 100, 1),
                        "left": round(bl * 100, 1),
                        "width": round(bw * 100, 1),
                        "height": round(bh * 100, 1),
                        "confidence": round(float(inst.get("Confidence", conf)) / 100.0, 2),
                    }
                else:
                    # Fallback default person bbox if Rekognition didn't return instance box
                    frame_bbox = {"top": 10.0, "left": 25.0, "width": 50.0, "height": 80.0, "confidence": round(conf / 100.0, 2)}

        if has_person:
            person_frames_count += 1
            if is_wide:
                wide_posture_count += 1
            if best_person is None or person_conf > best_person[0]:
                best_person = (person_conf, resized, frame_bbox)

        per_frame_results.append({
            "t": frame_t,
            "person": has_person,
            "confidence": round(person_conf / 100.0, 2) if has_person else 0.0,
            "box": frame_bbox,
            "wide_posture": is_wide,
            "labels": matched_signals,
        })

    # Keyframe selection: frame with highest person confidence, followed by peak motion frames
    keyframes = []
    if best_person:
        keyframes.append(best_person[1])
    for _, f in sorted(scored_samples, key=lambda t: -t[0]):
        if len(keyframes) >= n_keyframes:
            break
        if not any(np.array_equal(f, kf) for kf in keyframes):
            keyframes.append(f)

    ratios = [s[0] for s in scored_samples]
    arr = np.array(ratios) if ratios else np.array([0.0])
    total_eval = max(1, len(selected_indices))

    return {
        "frames_sampled": len(scored_samples),
        "duration_s": round(duration, 1),
        "motion_avg": round(float(arr.mean()), 4),
        "motion_peak": round(float(arr.max()), 4),
        "motion_frames_pct": round(100 * float((arr > 0.01).mean()), 1),
        "person_detected": person_frames_count > 0,
        "person_frames_pct": round(100 * person_frames_count / total_eval, 1),
        "wide_posture_frames_pct": round(100 * wide_posture_count / total_eval, 1),
        "bbox": best_person[2] if best_person else None,
        "keyframes": [_jpeg_b64(f) for f in keyframes[:n_keyframes]],
        "detector": "rekognition",
        "per_frame": per_frame_results,
    }


def analyze(
    source: FrameSource,
    sample_every=3,
    max_samples=240,
    n_keyframes=4,
    rekognition_client=None,
) -> dict:
    """Analyze video source using background motion gating + Amazon Rekognition (or OpenCV fallback)."""
    bg = cv2.createBackgroundSubtractorMOG2(history=100, varThreshold=32, detectShadows=False)
    scored = []
    duration = 0.0
    samples = 0

    for idx, ts, frame in source.frames():
        duration = ts
        if idx % sample_every:
            continue
        samples += 1
        if samples > max_samples:
            break
        small = cv2.resize(frame, (480, max(1, int(frame.shape[0] * 480 / frame.shape[1]))))
        mask = cv2.medianBlur(bg.apply(small), 5)
        if samples <= WARMUP:
            continue
        ratio = float((mask > 0).mean())
        scored.append((ratio, small))

    if not scored:
        return {"error": "no usable frames (clip too short or unreadable)"}

    backend_choice = os.getenv("VISION_BACKEND", "opencv").lower()

    if backend_choice == "rekognition":
        try:
            return _analyze_rekognition(
                scored,
                duration,
                n_keyframes=n_keyframes,
                rekognition_client=rekognition_client,
            )
        except Exception as e:
            err_name = type(e).__name__
            if hasattr(e, "response") and isinstance(e.response, dict):
                err_name = e.response.get("Error", {}).get("Code", err_name)
            logger.warning(f"Rekognition analysis failed ({err_name}); falling back to OpenCV HOG: {e}")
            return _analyze_opencv(
                scored,
                duration,
                n_keyframes=n_keyframes,
                detector_label=f"hog (rekognition failed: {err_name})",
            )

    return _analyze_opencv(scored, duration, n_keyframes=n_keyframes, detector_label="hog")