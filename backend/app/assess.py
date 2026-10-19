"""Rules-based evidence assessment engine.
Deterministic, template-driven evaluation of video analysis for caretaking and security.
No external LLMs or cloud AI models are used in this assessment path.
"""
import os
from typing import Any, Dict, List, Tuple

ANALYSIS_VERSION = "v2-rules"

STANDARD_LIMITATIONS = [
    "Single-frame detector; body posture estimated from 2D bounding boxes.",
    "Clip duration is limited to 10 seconds.",
    "Ring media contains a watermark overlay.",
    "Activity occurring outside the camera field of view is undetectable.",
]

WEAPON_LABELS = {"Weapon", "Gun", "Handgun", "Firearm", "Knife", "Dagger", "Blade"}
MASK_LABELS = {"Mask", "Gas Mask"}
INCIDENT_LABELS = {"Fighting", "Window - Broken", "Fire", "Smoke"}
KITCHEN_LABELS = {"Kitchen", "Cooking", "Food", "Culinary", "Chef"}


def _num(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _evaluate_security(per_frame: List[dict], min_conf: float) -> Tuple[str, List[dict], str, str]:
    """
    Evaluates security signals across frames with false-positive safeguards:
    - Requires confidence >= min_conf (default 80) in >= 2 frames, OR >= 90 in 1 frame.
    - Kitchen context downgrades knife detections.
    - Mask requires person present in that frame.
    Returns: (level, signals, highest_security_priority, notes)
    """
    weapon_hits = []
    mask_hits = []
    incident_hits = []
    kitchen_context_detected = False

    for f in per_frame:
        has_person = bool(f.get("person"))
        frame_t = f.get("t", 0.0)
        labels = f.get("labels", [])

        # Check for kitchen context anywhere in the clip
        for l in labels:
            if l.get("label") in KITCHEN_LABELS:
                kitchen_context_detected = True

        for l in labels:
            name = l.get("label", "")
            conf = _num(l.get("confidence"))

            if name in WEAPON_LABELS:
                weapon_hits.append({"label": name, "confidence": conf, "frame_t": frame_t})
            elif name in MASK_LABELS:
                # Mask only counts if person is present in that frame
                if has_person:
                    mask_hits.append({"label": name, "confidence": conf, "frame_t": frame_t})
            elif name in INCIDENT_LABELS:
                incident_hits.append({"label": name, "confidence": conf, "frame_t": frame_t})

    # Evaluate weapon hits
    valid_weapons = []
    weapon_downgraded_for_kitchen = False

    # Check high confidence single frame (>= 90) or multi-frame (>= min_conf in >= 2 frames)
    high_conf_weapons = [w for w in weapon_hits if w["confidence"] >= 90.0]
    multi_conf_weapons = [w for w in weapon_hits if w["confidence"] >= min_conf]

    qualifying_weapons = high_conf_weapons or (multi_conf_weapons if len(multi_conf_weapons) >= 2 else [])

    for w in qualifying_weapons:
        if w["label"] in ("Knife", "Blade", "Dagger") and kitchen_context_detected:
            weapon_downgraded_for_kitchen = True
        else:
            valid_weapons.append(w)

    # Evaluate mask hits
    high_conf_masks = [m for m in mask_hits if m["confidence"] >= 90.0]
    multi_conf_masks = [m for m in mask_hits if m["confidence"] >= min_conf]
    valid_masks = high_conf_masks or (multi_conf_masks if len(multi_conf_masks) >= 2 else [])

    # Evaluate incident hits
    high_conf_incidents = [i for i in incident_hits if i["confidence"] >= 90.0]
    multi_conf_incidents = [i for i in incident_hits if i["confidence"] >= min_conf]
    valid_incidents = high_conf_incidents or (multi_conf_incidents if len(multi_conf_incidents) >= 2 else [])

    all_confirmed = valid_weapons + valid_masks + valid_incidents
    if not all_confirmed:
        notes = "No qualifying security indicators."
        if weapon_downgraded_for_kitchen:
            notes = "Knife detected but kitchen context present; alert downgraded to routine."
        return "none", [], "low", notes

    notes_parts = []
    prio = "medium"
    if valid_weapons:
        notes_parts.append(f"Possible weapon detected ({valid_weapons[0]['label']} at {valid_weapons[0]['confidence']}%)")
        prio = "high"
    if valid_masks:
        notes_parts.append(f"Face covering detected on person ({valid_masks[0]['label']} at {valid_masks[0]['confidence']}%)")
        if prio != "high":
            prio = "medium"
    if valid_incidents:
        notes_parts.append(f"Incident indicator detected ({valid_incidents[0]['label']} at {valid_incidents[0]['confidence']}%)")
        prio = "high"

    return "possible", all_confirmed, prio, "; ".join(notes_parts)


def _evaluate_fall(
    person: bool,
    stationary_s: float,
    wide_pct: float,
    per_frame: List[dict],
    fall_still_s: float,
) -> Tuple[str, List[str], List[str]]:
    """
    Evaluates possible fall indicator:
    - (a) Explicit fall labels: Fallen Person, Injury, Crawling
    - (b) Geometry: wide posture (> 20%)
    - (c) Stillness: stationary duration >= fall_still_s
    - (d) Context: Floor/Ground present vs Bed/Couch/Sleeping present
    Returns: (level, signals, missed_signals)
    """
    if not person:
        return "none", [], ["No person detected"]

    signals = []
    missed = []
    has_explicit_fall_label = False
    has_floor_context = False
    has_bed_context = False

    for f in per_frame:
        for l in f.get("labels", []):
            name = l.get("label", "")
            conf = _num(l.get("confidence"))
            if name in ("Fallen Person", "Injury", "Crawling") and conf >= 65.0:
                has_explicit_fall_label = True
                signals.append(f"{name} label detected ({conf}%)")
            if name in ("Floor", "Flooring", "Ground") and conf >= 60.0:
                has_floor_context = True
            if name in ("Bed", "Couch", "Sleeping") and conf >= 65.0:
                has_bed_context = True

    is_wide = wide_pct >= 20.0
    if is_wide:
        signals.append(f"Horizontal/wide posture observed ({wide_pct}% of frames)")
    else:
        missed.append("Upright posture observed throughout")

    is_still = stationary_s >= fall_still_s
    if is_still:
        signals.append(f"Person stationary for {stationary_s}s (threshold {fall_still_s}s)")
    else:
        missed.append(f"Movement detected (stationary only {stationary_s}s)")

    if has_floor_context:
        signals.append("Floor/ground context identified")
    if has_bed_context:
        signals.append("Bed/couch resting context identified (lowers fall likelihood)")

    # Decision logic
    # Likely: explicit fall label + wide + still + floor context, or strong explicit fall + stillness
    if (has_explicit_fall_label and is_wide and is_still and not has_bed_context) or (
        is_wide and is_still and has_floor_context and not has_bed_context
    ):
        return "likely", signals, missed

    # Possible: wide + still, or explicit fall label alone
    if (is_wide and is_still) or has_explicit_fall_label:
        return "possible", signals, missed

    return "none", signals, missed


def assess(meta: dict, vision: dict) -> dict:
    """Perform deterministic, evidence-based assessment on video analysis results."""
    detector = vision.get("detector", "opencv")
    err = vision.get("error")

    # 1. Error fallback
    if err:
        ring_type = meta.get("ring_event_type", "motion")
        return {
            "summary": f"Ring reported {ring_type}, but no video could be analysed.",
            "observed_evidence": [f"Analysis error: {err}"],
            "priority": "low",
            "confidence": 0.1,
            "limitations": STANDARD_LIMITATIONS,
            "recommended_action": "No video could be analysed - please check manually in the Ring app.",
            "engine": "rules",
            "detector": detector,
            "analysis_version": ANALYSIS_VERSION,
            "fall_indicator": {"level": "none", "signals": [], "missed_signals": ["Video clip unavailable"]},
            "security_indicator": {"level": "none", "signals": [], "notes": "No video available"},
            "category": "caretaking",
        }

    # Configuration thresholds
    fall_still_s = _num(os.getenv("FALL_STILL_SECONDS", "5.0"))
    sec_min_conf = _num(os.getenv("SECURITY_MIN_CONFIDENCE", "80.0"))

    # Extract detector figures
    duration_s = _num(vision.get("duration_s"))
    motion_pct = _num(vision.get("motion_frames_pct"))
    motion_peak = _num(vision.get("motion_peak"))
    person = bool(vision.get("person_detected"))
    person_pct = _num(vision.get("person_frames_pct"))
    wide_pct = _num(vision.get("wide_posture_frames_pct"))
    stationary_s = round(duration_s * (1.0 - motion_pct / 100.0), 1) if person else 0.0
    per_frame = vision.get("per_frame", [])

    # Evaluate indicators
    fall_level, fall_signals, fall_missed = _evaluate_fall(
        person=person,
        stationary_s=stationary_s,
        wide_pct=wide_pct,
        per_frame=per_frame,
        fall_still_s=fall_still_s,
    )

    sec_level, sec_signals, sec_prio, sec_notes = _evaluate_security(
        per_frame=per_frame,
        min_conf=sec_min_conf,
    )

    # Compile concrete evidence points
    evidence = []
    if meta.get("ring_event_type"):
        sub = meta.get("ring_sub_type")
        evidence.append(f"Ring reported event: {meta['ring_event_type']}" + (f" ({sub})" if sub else ""))
    evidence.append(f"Vision detector: {detector} on {duration_s}s video clip")
    if person:
        evidence.append(f"Person bounding box confirmed in {person_pct}% of evaluated frames")
        if wide_pct > 0:
            evidence.append(f"Horizontal/low posture detected in {wide_pct}% of frames")
        if stationary_s > 0:
            evidence.append(f"Inactivity/stationary time: {stationary_s}s (motion across clip: {motion_pct}%)")
    else:
        evidence.append("No person detected by vision model")
        if motion_pct > 0:
            evidence.append(f"Environmental motion registered across {motion_pct}% of frames without person detected (peak score: {motion_peak})")

    for s in fall_signals:
        if s not in evidence:
            evidence.append(f"Fall indicator signal: {s}")

    for s in sec_signals:
        evidence.append(f"Security detection: {s['label']} ({s['confidence']}%) at {s.get('frame_t', 0)}s")

    # Determine Category
    is_sec = sec_level == "possible"
    is_fall = fall_level in ("possible", "likely")
    if is_sec and is_fall:
        category = "both"
    elif is_sec:
        category = "security"
    else:
        category = "caretaking"

    # Priority & Recommended Action Resolution
    reasons = []
    prio = "low"
    action = "No action needed."
    conf = 0.5

    if is_fall:
        prio = "high"
        conf = 0.85 if fall_level == "likely" else 0.70
        action = "Possible fall - please check now or call resident."
        reasons.append(f"Possible fall indicator ({fall_level}): horizontal body posture and stillness observed.")
    elif is_sec:
        prio = sec_prio
        conf = 0.80
        action = "Review security footage immediately - do not confront unknown individuals."
        reasons.append(f"Security indicator ({sec_notes}).")
    elif person and wide_pct > 20:
        prio = "medium"
        conf = 0.60
        action = "Review camera clip to check resident posture."
        reasons.append("Person observed in horizontal/low posture without prolonged stillness.")
    elif person and stationary_s > 6 and motion_pct < 15:
        prio = "medium"
        conf = 0.65
        action = "Check on resident to verify well-being."
        reasons.append(f"Person present with minimal movement for {stationary_s}s.")
    elif person:
        prio = "low"
        conf = 0.75
        action = "No action needed (routine ambulatory activity)."
        reasons.append("Routine person movement detected.")
    elif motion_pct > 5:
        prio = "low"
        conf = 0.50
        action = "No action needed."
        reasons.append("Environmental motion registered without person presence.")
    else:
        prio = "low"
        conf = 0.80
        action = "No action needed."
        reasons.append("Minor or normal ambient activity.")

    # Honest summary
    summary = " ".join(reasons)

    return {
        "summary": summary,
        "observed_evidence": evidence,
        "priority": prio,
        "confidence": conf,
        "limitations": STANDARD_LIMITATIONS,
        "recommended_action": action,
        "engine": "rules",
        "detector": detector,
        "analysis_version": ANALYSIS_VERSION,
        "fall_indicator": {
            "level": fall_level,
            "signals": fall_signals,
            "missed_signals": fall_missed,
        },
        "security_indicator": {
            "level": sec_level,
            "signals": sec_signals,
            "notes": sec_notes,
        },
        "category": category,
    }
