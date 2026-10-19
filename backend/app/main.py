import asyncio, hashlib, hmac, json, logging, os, re, time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import db, pipeline
from .notify import get_notifier, SnsNotifier, NtfyNotifier, TelegramNotifier
from .ring import RingAuthError, RingError, ring
from .schema import to_event

logger = logging.getLogger("ringcare.main")

subscribers: list[asyncio.Queue] = []
_device_cache = {"t": 0.0, "devices": []}
HOURS = ["12 AM", "03 AM", "06 AM", "09 AM", "12 PM", "03 PM", "06 PM", "09 PM"]
PRIORITY_ORDER = {"low": 1, "medium": 2, "high": 3}

# Shared Ring connection state (safe to read from health endpoint)
_ring_state: dict = {"status": "ok", "token_expired_logged": False, "last_poll_error": None}


def should_alert(prio: str) -> bool:
    min_prio = os.getenv("NOTIFY_MIN_PRIORITY", "medium").lower()
    return PRIORITY_ORDER.get(str(prio).lower(), 1) >= PRIORITY_ORDER.get(min_prio, 2)


def notify_initial(ev: dict):
    prio = (ev.get("severity") or ev.get("aiAssessment", {}).get("urgency") or "low").lower()
    if not should_alert(prio):
        return
    eid = ev.get("id")
    if not eid:
        return
    notifier = get_notifier()
    ok, err = notifier.send(ev, reminder_n=0)
    db.mark_alerted(eid, expected_reminders=0, error=err if not ok else None)


def _check_escalations():
    escalate_after_s = int(os.getenv("ESCALATE_AFTER_MIN", "5")) * 60
    max_reminders = int(os.getenv("MAX_REMINDERS", "3"))
    min_prio = os.getenv("NOTIFY_MIN_PRIORITY", "medium").lower()

    unacked = db.unacknowledged(limit=50)
    now = time.time()
    notifier = get_notifier()

    for r in unacked:
        if r.get("status") != "new":
            continue
        assessment = r.get("assessment", {})
        prio = (assessment.get("priority") or "low").lower()
        if PRIORITY_ORDER.get(prio, 1) < PRIORITY_ORDER.get(min_prio, 2):
            continue

        reminders = int(r.get("reminders") or 0)
        eid = r.get("event_id") or r.get("id")

        if reminders == 0:
            ok, err = notifier.send(r, reminder_n=0)
            db.mark_alerted(eid, expected_reminders=0, error=err if not ok else None)
        elif reminders < max_reminders:
            last_alert = r.get("last_alert_at") or r.get("event_ts") or now
            if (now - last_alert) >= escalate_after_s:
                next_reminder = reminders + 1
                ok, err = notifier.send(r, reminder_n=next_reminder)
                db.mark_alerted(eid, expected_reminders=reminders, error=err if not ok else None)


async def escalator():
    while True:
        await asyncio.sleep(30)
        try:
            await run_in_threadpool(_check_escalations)
        except Exception as e:
            logger.error(f"[escalator] Error in escalation cycle: {e}")


def publish(ev: dict):
    light = {**ev, "thumbnail": None}
    for q in list(subscribers):
        q.put_nowait(light)
    try:
        notify_initial(ev)
    except Exception as e:
        logger.warning(f"[notify] Initial alert dispatch error: {e}")


async def poller(seconds: int):
    while True:
        await asyncio.sleep(seconds)
        try:
            res = await run_in_threadpool(pipeline.sync_ring)
            # Successful poll: clear any previous expiry state
            _ring_state["status"] = "ok"
            _ring_state["token_expired_logged"] = False
            _ring_state["last_poll_error"] = None
            for i in res["ids"]:
                publish(to_event(db.get(i)))
        except RingAuthError as e:
            # Log token expiry only once to avoid log spam
            _ring_state["status"] = "token_expired"
            _ring_state["last_poll_error"] = e.message
            if not _ring_state["token_expired_logged"]:
                logger.warning(
                    "Ring token expired - paste a new one in the dashboard or POST /api/ring/token. "
                    f"(Detail: {e.message})"
                )
                _ring_state["token_expired_logged"] = True
        except RingError as e:
            _ring_state["last_poll_error"] = e.message
            logger.warning(f"[poll] Ring API error (will retry): {e.message}")
        except Exception as e:
            _ring_state["last_poll_error"] = str(e)
            logger.warning(f"[poll] Unexpected error (will retry): {e}")


@asynccontextmanager
async def lifespan(app):
    db.init()
    pipeline.ensure_sample_clips()
    poll_task = None
    secs = int(os.getenv("RING_POLL_SECONDS", "0") or 0)
    if secs > 0 and ring.configured:
        poll_task = asyncio.create_task(poller(secs))
    escalator_task = asyncio.create_task(escalator())
    yield
    if poll_task:
        poll_task.cancel()
    escalator_task.cancel()


app = FastAPI(title="RingCare AI", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["*"], allow_headers=["*"])


def _pid(eid: str) -> str:
    clean = str(eid).strip()
    if not clean:
        raise HTTPException(404, "Unknown event id")
    return clean


def _light(row):
    e = to_event(row)
    e["thumbnail"] = None
    return e


def _fail(e: Exception):
    if isinstance(e, RingAuthError):
        raise HTTPException(401, e.message)
    if isinstance(e, RingError):
        raise HTTPException(e.status if 400 <= e.status < 600 else 502, e.message)
    err_cls = e.__class__.__name__
    if "NoCredentialsError" in err_cls or "PartialCredentialsError" in err_cls:
        raise HTTPException(503, "AWS credentials not configured or expired.")
    if hasattr(e, "response") and isinstance(getattr(e, "response"), dict):
        err_info = getattr(e, "response").get("Error", {})
        code = err_info.get("Code", "AwsError")
        msg = err_info.get("Message", str(e))
        raise HTTPException(502, f"AWS service error ({code}): {msg}")
    raise HTTPException(500, f"Internal server error: {e}")


@app.exception_handler(RingAuthError)
async def ring_auth_error_handler(request: Request, exc: RingAuthError):
    return JSONResponse(status_code=401, content={"detail": exc.message})


@app.exception_handler(RingError)
async def ring_error_handler(request: Request, exc: RingError):
    status_code = exc.status if 400 <= exc.status < 600 else 502
    return JSONResponse(status_code=status_code, content={"detail": exc.message})


# ------------------------------------------------------------------ health / ring
@app.get("/api/health")
def health():
    backend = os.getenv("STORAGE_BACKEND", "sqlite")
    vision_backend = os.getenv("VISION_BACKEND", "opencv")
    notify_channels = [c.strip().lower() for c in os.getenv("NOTIFY_CHANNELS", "sns,ntfy").split(",") if c.strip()]
    if not ring.configured:
        ring_status = "not_configured"
    else:
        ring_status = _ring_state.get("status", "ok")

    storage_status = "ok"
    try:
        db.list_events(1)
    except Exception as exc:
        storage_status = f"unhealthy: {exc}"

    return {
        "ok": storage_status == "ok",
        "storage": backend,
        "storage_status": storage_status,
        "vision": vision_backend,
        "assessment": "rules",
        "ring": ring_status,
        "ring_status": ring_status,
        "ring_configured": ring.configured,
        "notify": notify_channels,
        "sns_configured": bool(os.getenv("SNS_TOPIC_ARN")),
        "sample_clips": [p.name for p in pipeline.sample_clips()],
    }


# ------------------------------------------------------------------ notifications
@app.get("/api/notify/config")
def notify_config():
    channels = [c.strip().lower() for c in os.getenv("NOTIFY_CHANNELS", "sns,ntfy").split(",") if c.strip()]
    topic_arn = os.getenv("SNS_TOPIC_ARN", "")
    masked_arn = f"{topic_arn[:15]}...{topic_arn[-8:]}" if len(topic_arn) > 25 else (topic_arn or "Not configured")
    return {
        "channels": channels,
        "sns_configured": bool(topic_arn),
        "sns_topic_arn": masked_arn,
        "min_priority": os.getenv("NOTIFY_MIN_PRIORITY", "medium"),
        "escalate_after_min": int(os.getenv("ESCALATE_AFTER_MIN", "5")),
        "max_reminders": int(os.getenv("MAX_REMINDERS", "3")),
        "resident_name": os.getenv("RESIDENT_NAME", "Eleanor Vance"),
    }


class NotifyTestBody(BaseModel):
    channel: str | None = None


@app.post("/api/notify/test")
async def notify_test(body: NotifyTestBody | None = None):
    test_event = {
        "id": "evt_test_alert",
        "cameraName": "Front Porch Camera",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "severity": "medium",
        "category": "caretaking",
        "summary": "RingCare notification pipeline operational test message.",
        "recommendedAction": "Verify that test notification was received on enabled channels.",
        "observed_evidence": ["Manual test triggered via /api/notify/test", "Channel verification payload"],
        "fallIndicator": {"level": "none", "signals": []},
        "securityIndicator": {"level": "none", "signals": []},
    }

    results = {}
    target = body.channel.lower().strip() if body and body.channel else None

    if not target or target == "sns":
        sns_notifier = SnsNotifier()
        ok, err = await run_in_threadpool(sns_notifier.send, test_event)
        results["sns"] = {"ok": ok, "error": err}

    if not target or target == "ntfy":
        ntfy_notifier = NtfyNotifier()
        ok, err = await run_in_threadpool(ntfy_notifier.send, test_event)
        results["ntfy"] = {"ok": ok, "error": err}

    if not target or target == "telegram":
        tg_notifier = TelegramNotifier()
        ok, err = await run_in_threadpool(tg_notifier.send, test_event)
        results["telegram"] = {"ok": ok, "error": err}

    overall_ok = any(r.get("ok") for r in results.values())
    return {"ok": overall_ok, "results": results}


class TokenBody(BaseModel):
    access_token: str


@app.post("/api/ring/token")
def set_token(body: TokenBody):
    ring.set_access_token(body.access_token)
    _device_cache["t"] = 0
    # Clear token-expiry state so the next poll succeeds without restarting
    _ring_state["status"] = "ok"
    _ring_state["token_expired_logged"] = False
    _ring_state["last_poll_error"] = None
    return {"ok": True}


def _devices(force=False):
    if not ring.configured:
        return []
    if force or time.time() - _device_cache["t"] > 60:
        devs = ring.devices()
        for d in devs:
            d["online"] = ring.device_online(d["id"])
        _device_cache.update(t=time.time(), devices=devs)
    return _device_cache["devices"]


@app.get("/api/ring/devices")
async def ring_devices():
    try:
        return await run_in_threadpool(_devices, True)
    except Exception as e:
        _fail(e)


class SyncBody(BaseModel):
    limit: int = 5


@app.post("/api/ring/sync")
async def ring_sync(body: SyncBody | None = None):
    try:
        res = await run_in_threadpool(pipeline.sync_ring, (body.limit if body else 5))
    except Exception as e:
        _fail(e)
    events = [to_event(db.get(i)) for i in res["ids"]]
    for e in events:
        publish(e)
    return {"added": len(events), "events": [{**e, "thumbnail": None} for e in events], "notes": res["notes"]}


async def _webhook_ingest(device_id: str, ring_event_id: str | None = None):
    try:
        # If a specific ring event id was provided, skip if already ingested
        if ring_event_id and db.has_ring_event(ring_event_id):
            logger.info(f"[webhook] Duplicate ring event {ring_event_id} - skipping ingestion")
            return
        res = await run_in_threadpool(pipeline.sync_ring, 3, 40, device_id)  # wait up to 40s for the clip
        for i in res["ids"]:
            publish(to_event(db.get(i)))
    except Exception as e:
        logger.warning(f"[webhook] Ingestion error for device {device_id}: {e}")


KNOWN_MOTION_TYPES = {"motion_detected", "motion", "on_demand", "ding"}


@app.post("/api/webhooks/ring")
async def ring_webhook(request: Request, bg: BackgroundTasks):
    raw = await request.body()
    key = os.getenv("RING_HMAC_KEY")
    if key:
        # Accept both 'sha256=<hex>' and raw '<hex>' formats from Ring
        actual = (request.headers.get("x-ring-signature") or request.headers.get("x-signature", "")).strip()
        if actual.startswith("sha256="):
            actual = actual[7:]
        expected = hmac.new(key.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, actual):
            raise HTTPException(401, "bad signature")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "invalid JSON")

    data = payload.get("data", payload)
    etype = (data.get("type") or "").lower()
    attrs = data.get("attributes", {}) or {}

    if etype not in KNOWN_MOTION_TYPES:
        return {"status": "ignored", "reason": f"unsupported event type: {etype}"}

    ring_event_id = str(data.get("id", "")) or None
    # Immediately reject known duplicates before spawning a background task
    if ring_event_id and db.has_ring_event(ring_event_id):
        return {"status": "ignored", "reason": "duplicate event"}

    did = attrs.get("device_id") or re.sub(rf"_{etype}_\d+$", "", str(data.get("id", "")))
    if did:
        bg.add_task(_webhook_ingest, did, ring_event_id)  # reply 200 immediately (Ring requires <5s)
    return {"status": "ok"}


# ------------------------------------------------------------------ events
class SimBody(BaseModel):
    video: str | None = None


@app.post("/api/events/simulate")
async def simulate(body: SimBody | None = None):
    try:
        rid = await run_in_threadpool(pipeline.simulate, body.video if body else None)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    ev = to_event(db.get(rid))
    publish(ev)
    return ev


@app.get("/api/events")
def events():
    return [_light(r) for r in db.list_events(100)]


@app.get("/api/events/{eid}")
def event(eid: str):
    r = db.get(_pid(eid))
    if not r:
        raise HTTPException(404, "Event not found")
    return to_event(r)


@app.get("/api/events/{eid}/clip")
def clip(eid: str):
    r = db.get(_pid(eid))
    if not r or not r.get("clip_file"):
        raise HTTPException(404, "No clip recorded for this event")
    path = pipeline.CLIPS / Path(r["clip_file"]).name
    if not path.exists():
        raise HTTPException(404, "Clip file missing on disk")
    media_type = "video/webm" if path.suffix == ".webm" else "video/mp4"
    return FileResponse(path, media_type=media_type, headers={"Accept-Ranges": "bytes"})


class ActionBody(BaseModel):
    note: str | None = None


@app.post("/api/events/{eid}/{action}")
def act(eid: str, action: str, body: ActionBody | None = None):
    if action not in ("acknowledge", "dismiss"):
        raise HTTPException(400, "action must be acknowledge or dismiss")
    i = _pid(eid)
    if not db.get(i):
        raise HTTPException(404, "Event not found")
    note = (body.note if body else None) or (
        "Acknowledged by caregiver via dashboard." if action == "acknowledge" else "Dismissed as non-critical by caregiver.")
    db.set_status(i, "acknowledged" if action == "acknowledge" else "dismissed", note)
    updated = db.get(i)
    if not updated:
        raise HTTPException(500, "Failed to retrieve event after status update")
    return _light(updated)


@app.post("/api/reset")
def reset():
    db.clear()
    return {"ok": True}


# ------------------------------------------------------------------ settings
@app.get("/api/settings")
def get_settings():
    return db.get_settings()


@app.put("/api/settings")
def update_settings(settings: dict):
    return db.put_settings(settings)


# ------------------------------------------------------------------ cameras / summary / chart
@app.get("/api/cameras")
def cameras():
    evs = [_light(r) for r in db.list_events(100)]
    try:
        devs = _devices()
    except Exception:
        devs = list(_device_cache["devices"])
    known = {d["id"]: {"name": d["name"], "online": d.get("online")} for d in devs}
    for e in evs:
        known.setdefault(e["cameraId"], {"name": e["cameraName"], "online": True})
    if not known:
        known["local-sample"] = {"name": "Local sample camera", "online": True}
    out = []
    for cid, info in known.items():
        mine = [e for e in evs if e["cameraId"] == cid]
        out.append({
            "id": cid, "name": info["name"],
            "location": "Ring device" if ring.configured and not cid.startswith("local") else "Local sample clips",
            "status": "offline" if info["online"] is False else "online",
            "lastActivity": mine[0]["timestamp"] if mine else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "motionEventsToday": len(mine), "reviewEventsToday": sum(e["aiStatus"] == "review" for e in mine),
            "resolution": "Ring media (watermarked)" if not cid.startswith("local") else "Synthetic sample",
            "signalStrength": "good", "firmwareVersion": "n/a", "zoneTags": []})
    return out


@app.get("/api/dashboard/summary")
def summary():
    evs = [_light(r) for r in db.list_events(100)]
    cams = cameras()
    review = sum(e["aiStatus"] == "review" for e in evs)
    return {"todayEventsCount": len(evs), "requiresReviewCount": review, "normalActivityCount": len(evs) - review,
            "camerasOnlineCount": sum(c["status"] == "online" for c in cams), "totalCamerasCount": len(cams),
            "lastUpdated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "monitoringActive": True}


@app.get("/api/analytics/hourly-activity")
def hourly():
    buckets = [{"hourLabel": h, "totalEvents": 0, "reviewEvents": 0, "normalEvents": 0, "motionAverage": 0.0} for h in HOURS]
    sums = [0.0] * 8
    for r in db.list_events(100):
        e = _light(r)
        i = time.localtime(r["event_ts"]).tm_hour // 3
        b = buckets[i]
        b["totalEvents"] += 1
        b["reviewEvents" if e["aiStatus"] == "review" else "normalEvents"] += 1
        sums[i] += e["motionScore"]
    for i, b in enumerate(buckets):
        b["motionAverage"] = round(sums[i] / b["totalEvents"], 2) if b["totalEvents"] else 0.0
    return buckets


# ------------------------------------------------------------------ live updates
@app.get("/api/stream")
async def stream():
    q: asyncio.Queue = asyncio.Queue()
    subscribers.append(q)

    async def gen():
        try:
            while True:
                try:
                    yield f"data: {json.dumps(await asyncio.wait_for(q.get(), 15))}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            subscribers.remove(q)

    return StreamingResponse(gen(), media_type="text/event-stream")
