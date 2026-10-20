"""Convert DB rows into the exact `Event` shape the React dashboard expects (src/types/events.ts)."""
import hashlib
from datetime import datetime, timezone
URGENCY = {"low": "routine", "medium": "prompt", "high": "immediate"}
LABEL = {"low": "Routine Activity", "medium": "Review Recommended", "high": "Immediate Attention Advised"}
def iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
def _num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default
def _video_status(r: dict, err: bool) -> str:
    if r.get("video_status"):
        return r["video_status"]
    source = r.get("source", "")
    clip_file = r.get("clip_file")
    if source in ("simulated", "ring+sample-clip"):
        return "sample"
    if err or not clip_file:
        return "unavailable"
    if ".play." in clip_file or clip_file.endswith(".webm"):
        return "converted"
    if source == "ring":
        return "ring_clip"
    return "converted" if clip_file else "unavailable"
def to_event(r: dict) -> dict:
    v, a = r["vision"], r["assessment"]
    prio = a.get("priority", "low")
    err = bool(v.get("error"))
    person = bool(v.get("person_detected"))
    motion_pct = _num(v.get("motion_frames_pct"))
    motion_score = round(min(1.0, _num(v.get("motion_peak")) * 4), 2)
    stationary = round(_num(v.get("duration_s")) * (1 - motion_pct / 100), 1) if person else 0.0
    wide = _num(v.get("wide_posture_frames_pct"))
    posture = None if err else ("floor_level" if wide > 20 else "ambulatory" if motion_pct > 40
                                else "standing" if person else None)
    etype = "person" if person else "motion"
    if person and stationary > 5 and motion_pct < 20:
        etype = "stationary"
    raw_id = str(r.get("id") or r.get("event_id") or "0")
    if raw_id.startswith("evt_"):
        eid = raw_id
    elif raw_id.startswith("ring#"):
        short_hash = hashlib.sha256(raw_id[5:].encode("utf-8")).hexdigest()[:12]
        eid = f"evt_{short_hash}"
    elif raw_id.startswith("sim#"):
        eid = f"evt_{raw_id[4:]}"
    else:
        eid = f"evt_{raw_id}"
    boxes = []
    b = v.get("bbox")
    if b:
        color = "#ef4444" if prio == "high" else "#f59e0b" if prio == "medium" else "#10b981"
        boxes = [{"id": f"box_{eid}", "label": "Person", "confidence": b.get("confidence", 0.5), "color": color,
                  "rect": {k: b[k] for k in ("top", "left", "width", "height")}}]
    status = r["status"] if r["status"] in ("acknowledged", "dismissed") else ("review" if prio != "low" else "normal")
    evidence = a.get("observed_evidence") or a.get("reasons", [])
    rationale = "; ".join(evidence) or "No notable indicators."
    if r["source"] == "ring+sample-clip":
        rationale = "[Ring clip unavailable - analysed a local SAMPLE clip] " + rationale
    v_status = _video_status(r, err)
    rec_action = a.get("recommended_action") or a.get("suggested_action", "")
    category = a.get("category", "caretaking")
    # Map indicators if present
    fall_indicator = a.get("fall_indicator")
    if fall_indicator:
        fall_indicator = {
            "level": fall_indicator.get("level", "none"),
            "signals": fall_indicator.get("signals", []),
            "missedSignals": fall_indicator.get("missed_signals", []),
        }
    security_indicator = a.get("security_indicator")
    if security_indicator:
        security_indicator = {
            "level": security_indicator.get("level", "none"),
            "signals": security_indicator.get("signals", []),
            "notes": security_indicator.get("notes", ""),
        }
    ev = {
        "id": eid, "cameraId": r["device_id"], "cameraName": r["device_name"] or r["device_id"],
        "eventType": etype, "timestamp": iso(r["event_ts"]), "personDetected": person,
        "motionScore": motion_score, "stationaryDuration": stationary,
        "aiStatus": status, "severity": prio, "summary": a.get("summary", ""),
        "recommendedAction": rec_action,
        "category": category,
        "fallIndicator": fall_indicator,
        "securityIndicator": security_indicator,
        "cvAnalysis": {"personDetected": person, "motionDetected": motion_pct > 1, "motionScore": motion_score,
                       "stationaryDuration": stationary, "confidence": round(_num(a.get("confidence"), 0.4), 2),
                       "primaryZone": "Camera view", "boundingBoxes": boxes,
                       **({"postureEstimation": posture} if posture else {})},
        "aiAssessment": {"statusLabel": LABEL.get(prio, "Review Recommended"), "summary": a.get("summary", ""),
                         "recommendedAction": rec_action, "urgency": URGENCY.get(prio, "prompt"),
                         "rationale": rationale, "evidence": evidence,
                         "limitations": a.get("limitations", []),
                         "analysisVersion": a.get("analysis_version", "v2-rules")},
        "source": r["source"], "videoStatus": v_status, "engine": a.get("engine", "rules"),
        "thumbnail": r.get("thumbnail"),
        "clipUrl": f"/api/events/{eid}/clip" if r.get("clip_file") else None,
    }
    if r["status"] in ("acknowledged", "dismissed") and r.get("acted_at"):
        ev["actionLog"] = {"action": r["status"], "timestamp": iso(r["acted_at"]),
                           "caregiverNote": r.get("note") or "", "actor": r.get("actor") or "Primary Caregiver"}
    return ev
