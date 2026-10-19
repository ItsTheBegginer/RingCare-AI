import os
import pytest
from app.assess import assess, ANALYSIS_VERSION


def test_assess_no_motion():
    meta = {"ring_event_type": "motion"}
    vision = {
        "duration_s": 10.0,
        "motion_frames_pct": 0.0,
        "motion_peak": 0.0,
        "person_detected": False,
        "person_frames_pct": 0.0,
        "wide_posture_frames_pct": 0.0,
        "detector": "rekognition",
        "per_frame": [],
    }
    res = assess(meta, vision)
    assert res["priority"] == "low"
    assert res["engine"] == "rules"
    assert res["category"] == "caretaking"
    assert res["fall_indicator"]["level"] == "none"
    assert res["security_indicator"]["level"] == "none"
    assert "No action needed" in res["recommended_action"]


def test_assess_motion_without_person():
    meta = {"ring_event_type": "motion"}
    vision = {
        "duration_s": 10.0,
        "motion_frames_pct": 35.0,
        "motion_peak": 0.45,
        "person_detected": False,
        "person_frames_pct": 0.0,
        "wide_posture_frames_pct": 0.0,
        "detector": "rekognition",
        "per_frame": [],
    }
    res = assess(meta, vision)
    assert res["priority"] == "low"
    assert res["category"] == "caretaking"
    assert any("Environmental motion" in r or "without person" in r for r in res["observed_evidence"])


def test_assess_person_moving_normally():
    meta = {"ring_event_type": "person", "ring_sub_type": "human"}
    vision = {
        "duration_s": 10.0,
        "motion_frames_pct": 60.0,
        "motion_peak": 0.8,
        "person_detected": True,
        "person_frames_pct": 85.0,
        "wide_posture_frames_pct": 0.0,
        "detector": "rekognition",
        "per_frame": [{"person": True, "t": 1.0, "labels": [{"label": "Standing", "confidence": 95.0}]}],
    }
    res = assess(meta, vision)
    assert res["priority"] == "low"
    assert res["category"] == "caretaking"
    assert res["fall_indicator"]["level"] == "none"
    assert "routine" in res["summary"].lower() or "movement" in res["summary"].lower()


def test_assess_possible_fall():
    meta = {"ring_event_type": "motion"}
    # Person present, stationary for 9.0s (> 5s threshold), wide posture in 35% of frames
    vision = {
        "duration_s": 10.0,
        "motion_frames_pct": 10.0,
        "motion_peak": 0.2,
        "person_detected": True,
        "person_frames_pct": 75.0,
        "wide_posture_frames_pct": 35.0,
        "detector": "rekognition",
        "per_frame": [
            {"person": True, "t": 1.0, "labels": []},
            {"person": True, "t": 3.0, "labels": []},
        ],
    }
    res = assess(meta, vision)
    assert res["priority"] == "high"
    assert res["fall_indicator"]["level"] in ("possible", "likely")
    assert "Possible fall" in res["recommended_action"]


def test_assess_likely_fall_with_floor_context():
    meta = {"ring_event_type": "motion"}
    vision = {
        "duration_s": 10.0,
        "motion_frames_pct": 5.0,
        "motion_peak": 0.15,
        "person_detected": True,
        "person_frames_pct": 80.0,
        "wide_posture_frames_pct": 50.0,
        "detector": "rekognition",
        "per_frame": [
            {"person": True, "t": 2.0, "labels": [{"label": "Floor", "confidence": 92.0}]},
            {"person": True, "t": 5.0, "labels": [{"label": "Fallen Person", "confidence": 75.0}]},
        ],
    }
    res = assess(meta, vision)
    assert res["priority"] == "high"
    assert res["fall_indicator"]["level"] == "likely"
    assert any("Floor" in s for s in res["fall_indicator"]["signals"])


def test_assess_video_analysis_error():
    meta = {"ring_event_type": "motion"}
    vision = {"error": "Corrupted video file"}
    res = assess(meta, vision)
    assert res["priority"] == "low"
    assert "no video could be analysed" in res["summary"].lower()
    assert "check manually" in res["recommended_action"].lower()
    assert res["confidence"] <= 0.2


def test_assess_weapon_security_alert():
    meta = {"ring_event_type": "motion"}
    # Two frames with Weapon >= 80% confidence
    vision = {
        "duration_s": 10.0,
        "motion_frames_pct": 20.0,
        "motion_peak": 0.3,
        "person_detected": True,
        "person_frames_pct": 50.0,
        "wide_posture_frames_pct": 0.0,
        "detector": "rekognition",
        "per_frame": [
            {"person": True, "t": 1.0, "labels": [{"label": "Gun", "confidence": 88.0}]},
            {"person": True, "t": 3.0, "labels": [{"label": "Firearm", "confidence": 84.0}]},
        ],
    }
    res = assess(meta, vision)
    assert res["category"] in ("security", "both")
    assert res["priority"] == "high"
    assert res["security_indicator"]["level"] == "possible"
    assert len(res["security_indicator"]["signals"]) >= 2


def test_assess_knife_in_kitchen_downgraded():
    meta = {"ring_event_type": "motion"}
    # Knife present but Kitchen label also detected -> downgraded
    vision = {
        "duration_s": 10.0,
        "motion_frames_pct": 25.0,
        "motion_peak": 0.4,
        "person_detected": True,
        "person_frames_pct": 70.0,
        "wide_posture_frames_pct": 0.0,
        "detector": "rekognition",
        "per_frame": [
            {"person": True, "t": 2.0, "labels": [{"label": "Knife", "confidence": 86.0}, {"label": "Kitchen", "confidence": 90.0}]},
            {"person": True, "t": 4.0, "labels": [{"label": "Knife", "confidence": 84.0}]},
        ],
    }
    res = assess(meta, vision)
    # Should not trigger high security priority because of kitchen context
    assert res["priority"] != "high"
    assert "kitchen" in res["security_indicator"]["notes"].lower()


def test_assess_mask_requires_person():
    meta = {"ring_event_type": "motion"}
    # Mask label detected on a frame where NO person is detected -> ignored
    vision_no_person = {
        "duration_s": 10.0,
        "motion_frames_pct": 10.0,
        "motion_peak": 0.2,
        "person_detected": False,
        "person_frames_pct": 0.0,
        "wide_posture_frames_pct": 0.0,
        "detector": "rekognition",
        "per_frame": [
            {"person": False, "t": 1.0, "labels": [{"label": "Mask", "confidence": 92.0}]},
        ],
    }
    res1 = assess(meta, vision_no_person)
    assert res1["security_indicator"]["level"] == "none"

    # Mask detected WITH person -> qualifies for security indicator
    vision_with_person = {
        "duration_s": 10.0,
        "motion_frames_pct": 15.0,
        "motion_peak": 0.2,
        "person_detected": True,
        "person_frames_pct": 50.0,
        "wide_posture_frames_pct": 0.0,
        "detector": "rekognition",
        "per_frame": [
            {"person": True, "t": 1.0, "labels": [{"label": "Mask", "confidence": 92.0}]},
        ],
    }
    res2 = assess(meta, vision_with_person)
    assert res2["security_indicator"]["level"] == "possible"
    assert res2["category"] in ("security", "both")


def test_schema_standard_keys():
    meta = {"ring_event_type": "motion"}
    vision = {
        "duration_s": 10.0,
        "motion_frames_pct": 5.0,
        "motion_peak": 0.1,
        "person_detected": True,
        "person_frames_pct": 50.0,
        "wide_posture_frames_pct": 0.0,
        "detector": "rekognition",
        "per_frame": [],
    }
    res = assess(meta, vision)
    required = [
        "summary",
        "observed_evidence",
        "priority",
        "confidence",
        "limitations",
        "recommended_action",
        "engine",
        "detector",
        "analysis_version",
        "fall_indicator",
        "security_indicator",
        "category",
    ]
    for key in required:
        assert key in res, f"Missing standard assessment key: {key}"
    assert res["engine"] == "rules"
    assert res["analysis_version"] == ANALYSIS_VERSION
