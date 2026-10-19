"""Phase 9 — Optional Amazon Bedrock review agent.

Disabled by default (AGENT_ENABLED=false). When enabled, runs AFTER
notify_initial() as a background task and annotates the event with an
AI second opinion. It can NEVER change priority, status, or trigger alerts.
"""
from __future__ import annotations

import json
import logging
import os
import time
from threading import Lock
from typing import Any

logger = logging.getLogger("ringcare.agent")

# ---------------------------------------------------------------------------
# Daily cap tracking (in-process, resets on restart)
# ---------------------------------------------------------------------------
_cap_lock = Lock()
_cap_day: str = ""          # YYYY-MM-DD
_cap_count: int = 0


def _cap_exceeded() -> bool:
    """Return True if we have already hit AGENT_DAILY_CAP today."""
    global _cap_day, _cap_count
    today = time.strftime("%Y-%m-%d")
    daily_cap = int(os.getenv("AGENT_DAILY_CAP", "50"))
    with _cap_lock:
        if _cap_day != today:
            _cap_day = today
            _cap_count = 0
        return _cap_count >= daily_cap


def _cap_increment():
    global _cap_count
    with _cap_lock:
        _cap_count += 1


# ---------------------------------------------------------------------------
# Priority helpers
# ---------------------------------------------------------------------------
_PRIORITY_ORDER = {"low": 1, "medium": 2, "high": 3}


def _clamp_priority(suggested: str, rules: str) -> str:
    """Never let the agent lower priority below what the rules engine set."""
    s = str(suggested).lower().strip()
    r = str(rules).lower().strip()
    if _PRIORITY_ORDER.get(s, 1) < _PRIORITY_ORDER.get(r, 1):
        logger.warning(
            "[agent] Agent suggested priority '%s' is below rules priority '%s' — clamping.",
            s, r,
        )
        return r
    return s


# ---------------------------------------------------------------------------
# Eligibility check
# ---------------------------------------------------------------------------

def _is_eligible(ev: dict) -> bool:
    """Return True if this event qualifies for an agent review."""
    assessment = ev.get("assessment") or {}
    prio = (assessment.get("priority") or ev.get("severity") or "low").lower()
    if _PRIORITY_ORDER.get(prio, 1) >= 2:  # medium or high
        return True
    fall = assessment.get("fall_indicator") or {}
    if fall.get("level") in ("possible", "likely"):
        return True
    sec = assessment.get("security_indicator") or {}
    if sec.get("level") == "possible":
        return True
    return False


# ---------------------------------------------------------------------------
# Read-only tool implementations
# ---------------------------------------------------------------------------

def _make_tools(ev: dict):
    """Return the three read-only tools as plain callables (not Strands tool objects).
    The actual Strands @tool decorator wrapping happens below.
    """
    from . import db  # local import to keep module importable without db init

    def get_event_evidence(event_id: str) -> str:  # noqa: ANN001
        """Return stored labels, confidences, per_frame data, rule outputs, Ring metadata for the event."""
        row = db.get(event_id)
        if not row:
            return json.dumps({"error": "event not found"})
        v = row.get("vision") or {}
        a = row.get("assessment") or {}
        evidence = {
            "event_id": event_id,
            "labels": v.get("labels", []),
            "confidences": v.get("confidences", []),
            "per_frame": v.get("per_frame", []),
            "motion_frames_pct": v.get("motion_frames_pct"),
            "motion_peak": v.get("motion_peak"),
            "person_detected": v.get("person_detected"),
            "duration_s": v.get("duration_s"),
            "rule_outputs": {
                "priority": a.get("priority"),
                "fall_indicator": a.get("fall_indicator"),
                "security_indicator": a.get("security_indicator"),
                "summary": a.get("summary"),
                "observed_evidence": a.get("observed_evidence"),
            },
            "source": row.get("source"),
            "device_name": row.get("device_name"),
        }
        return json.dumps(evidence)

    def get_recent_events(camera_id: str, minutes: int) -> str:  # noqa: ANN001
        """Return up to 10 recent event summaries from this camera."""
        all_events = db.list_events(50)
        cutoff = time.time() - (max(1, int(minutes)) * 60)
        camera_events = [
            r for r in all_events
            if r.get("device_id") == camera_id and (r.get("event_ts") or 0) >= cutoff
        ][:10]
        summaries = []
        for r in camera_events:
            a = r.get("assessment") or {}
            summaries.append({
                "id": r.get("id"),
                "event_ts": r.get("event_ts"),
                "priority": a.get("priority"),
                "summary": a.get("summary"),
                "status": r.get("status"),
            })
        return json.dumps(summaries)

    def get_keyframes(event_id: str) -> str:  # noqa: ANN001
        """Return up to 4 stored JPEG keyframes as base64 strings."""
        row = db.get(event_id)
        if not row:
            return json.dumps({"error": "event not found"})
        v = row.get("vision") or {}
        keyframes = v.get("keyframes", [])
        # Each keyframe is already base64 JPEG; return up to 4
        return json.dumps({"keyframes": keyframes[:4], "count": min(len(keyframes), 4)})

    return get_event_evidence, get_recent_events, get_keyframes


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
VALID_AGREEMENTS = {"agrees", "disagrees", "uncertain"}
VALID_PRIORITIES = {"low", "medium", "high"}


def _validate_output(raw: Any, rules_priority: str) -> dict:
    """Validate and sanitise agent JSON output.  Returns validated dict."""
    if not isinstance(raw, dict):
        raise ValueError(f"Expected dict, got {type(raw).__name__}")

    agrees = raw.get("agrees_with_rules", "uncertain")
    if agrees not in VALID_AGREEMENTS:
        agrees = "uncertain"

    # Observations must each have text + evidence_ref; drop malformed ones
    obs_raw = raw.get("observations") or []
    observations = [
        {"text": str(o["text"]), "evidence_ref": str(o["evidence_ref"])}
        for o in obs_raw
        if isinstance(o, dict) and o.get("text") and o.get("evidence_ref")
    ]

    fp_reasons = [str(s) for s in (raw.get("possible_false_positive_reasons") or []) if s]

    suggested_action = str(raw.get("suggested_action") or "")

    suggested_priority = str(raw.get("suggested_priority") or "low").lower()
    if suggested_priority not in VALID_PRIORITIES:
        suggested_priority = rules_priority
    suggested_priority = _clamp_priority(suggested_priority, rules_priority)

    try:
        confidence = float(raw.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.5

    model_id = str(raw.get("model_id") or os.getenv("BEDROCK_MODEL_ID", ""))

    return {
        "agrees_with_rules": agrees,
        "observations": observations,
        "possible_false_positive_reasons": fp_reasons,
        "suggested_action": suggested_action,
        "suggested_priority": suggested_priority,
        "confidence": confidence,
        "model_id": model_id,
        "status": "ok",
        "created_at": time.time(),
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def maybe_review(ev: dict) -> None:
    """Run the Bedrock review agent for this event, if enabled and eligible.

    Always returns without raising — any failure is stored as 'unavailable'.
    Must be called AFTER notify_initial() has already fired.
    """
    # Guard 1: agent must be explicitly enabled
    if os.getenv("AGENT_ENABLED", "false").lower() != "true":
        return

    from . import db  # late import — keeps module importable without db

    eid = ev.get("id")
    if not eid:
        logger.warning("[agent] Event has no id — skipping.")
        return

    # Guard 2: only eligible events
    if not _is_eligible(ev):
        logger.debug("[agent] Event %s not eligible for review.", eid)
        return

    # Guard 3: daily cap
    if _cap_exceeded():
        logger.info("[agent] Daily cap reached — storing skipped_cap for %s.", eid)
        db.set_agent_review(eid, {
            "status": "skipped_cap",
            "created_at": time.time(),
            "model_id": os.getenv("BEDROCK_MODEL_ID", ""),
        })
        return

    assessment = ev.get("assessment") or {}
    rules_priority = (assessment.get("priority") or "low").lower()

    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run_agent, ev, eid, rules_priority)
            timeout_s = int(os.getenv("AGENT_TIMEOUT_S", "30"))
            result = future.result(timeout=timeout_s)
        _cap_increment()
        db.set_agent_review(eid, result)
        logger.info("[agent] Review stored for %s: %s", eid, result.get("status"))
    except concurrent.futures.TimeoutError:
        logger.warning("[agent] Agent timed out for event %s.", eid)
        db.set_agent_review(eid, {"status": "unavailable", "created_at": time.time()})
    except Exception as exc:
        logger.warning("[agent] Unexpected error for event %s: %s", eid, exc)
        db.set_agent_review(eid, {"status": "unavailable", "created_at": time.time()})


def _run_agent(ev: dict, eid: str, rules_priority: str) -> dict:
    """Inner function: actually invoke the Strands agent.
    Called inside a ThreadPoolExecutor so the timeout can be enforced.
    """
    from strands import Agent
    from strands.models import BedrockModel
    from strands.tools import tool as strands_tool

    get_event_evidence_fn, get_recent_events_fn, get_keyframes_fn = _make_tools(ev)

    # Wrap bare callables as Strands tools
    get_event_evidence = strands_tool(get_event_evidence_fn)
    get_recent_events = strands_tool(get_recent_events_fn)
    get_keyframes = strands_tool(get_keyframes_fn)

    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    region = os.getenv("BEDROCK_REGION", "us-east-1")

    bedrock_model = BedrockModel(model_id=model_id, region_name=region)

    agent = Agent(
        model=bedrock_model,
        tools=[get_event_evidence, get_recent_events, get_keyframes],
        system_prompt=(
            "You are a care-home security and fall-detection second-opinion reviewer. "
            "You have READ-ONLY tools. You CANNOT acknowledge, dismiss, alert, or notify anyone. "
            "Your role is purely advisory — the rules engine has already sent any alert. "
            "Analyse the event evidence and return a JSON object with exactly these fields: "
            "agrees_with_rules (agrees|disagrees|uncertain), "
            "observations (list of {text, evidence_ref}), "
            "possible_false_positive_reasons (list of str), "
            "suggested_action (str), "
            "suggested_priority (low|medium|high), "
            "confidence (0.0-1.0), "
            "model_id (str). "
            "Return ONLY the JSON object with no prose, no markdown fences."
        ),
    )

    prompt = (
        f"Review event {eid}. "
        f"Use get_event_evidence('{eid}') to fetch the stored evidence, "
        f"get_recent_events for camera context, and get_keyframes if useful. "
        f"Return the JSON review object."
    )

    response = agent(prompt)
    # Extract the final text output from the agent
    raw_text = str(response).strip()

    # Strip markdown fences if the model wrapped the output
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("[agent] Invalid JSON from agent for %s: %s", eid, exc)
        return {"status": "invalid", "created_at": time.time(), "model_id": model_id}

    try:
        validated = _validate_output(raw, rules_priority)
        validated["model_id"] = validated.get("model_id") or model_id
        return validated
    except Exception as exc:
        logger.warning("[agent] Validation failed for %s: %s", eid, exc)
        return {"status": "invalid", "created_at": time.time(), "model_id": model_id}
