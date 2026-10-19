"""Tests for Phase 9 — optional Bedrock review agent (app.agent).

All tests use mocked Strands Agent — never call real Bedrock.
"""
import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest

from app.agent import (
    _cap_exceeded,
    _clamp_priority,
    _is_eligible,
    _validate_output,
    maybe_review,
)
import app.agent as agent_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ev(priority="medium", fall_level="none", sec_level="none", eid="evt_test001"):
    return {
        "id": eid,
        "severity": priority,
        "assessment": {
            "priority": priority,
            "fall_indicator": {"level": fall_level},
            "security_indicator": {"level": sec_level},
        },
    }


def _reset_cap():
    """Reset the in-process daily cap counters between tests."""
    with agent_module._cap_lock:
        agent_module._cap_day = ""
        agent_module._cap_count = 0


# ---------------------------------------------------------------------------
# 1. Agent disabled (AGENT_ENABLED=false) → returns immediately, no Bedrock call
# ---------------------------------------------------------------------------

def test_agent_disabled_no_call(monkeypatch):
    """With AGENT_ENABLED=false, maybe_review must return without touching Bedrock."""
    monkeypatch.setenv("AGENT_ENABLED", "false")
    _reset_cap()

    with patch("app.agent._run_agent") as mock_run, \
         patch("app.db.set_agent_review") as mock_set:
        maybe_review(_ev())
        mock_run.assert_not_called()
        mock_set.assert_not_called()


# ---------------------------------------------------------------------------
# 2. Daily cap exceeded → stores status: skipped_cap
# ---------------------------------------------------------------------------

def test_daily_cap_exceeded(monkeypatch):
    monkeypatch.setenv("AGENT_ENABLED", "true")
    monkeypatch.setenv("AGENT_DAILY_CAP", "0")  # cap of 0 is always exceeded
    _reset_cap()

    stored = {}

    def fake_set_agent_review(eid, review):
        stored["eid"] = eid
        stored["review"] = review

    with patch("app.db.set_agent_review", side_effect=fake_set_agent_review):
        maybe_review(_ev())

    assert stored.get("review", {}).get("status") == "skipped_cap"


# ---------------------------------------------------------------------------
# 3. suggested_priority lower than rules priority → clamped and logs WARNING
# ---------------------------------------------------------------------------

def test_clamp_priority_warns(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="ringcare.agent"):
        result = _clamp_priority("low", "high")
    assert result == "high"
    assert "clamping" in caplog.text.lower()


def test_clamp_priority_no_warn_equal(caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="ringcare.agent"):
        result = _clamp_priority("high", "high")
    assert result == "high"
    assert "clamping" not in caplog.text.lower()


def test_clamp_priority_higher_allowed():
    result = _clamp_priority("high", "medium")
    assert result == "high"


# ---------------------------------------------------------------------------
# 4. Tool list contains only the 3 read-only tools
# ---------------------------------------------------------------------------

def test_tool_names():
    from app.agent import _make_tools
    ev = _ev()
    with patch("app.db.get", return_value=None), \
         patch("app.db.list_events", return_value=[]):
        fns = _make_tools(ev)
    names = {fn.__name__ for fn in fns}
    assert names == {"get_event_evidence", "get_recent_events", "get_keyframes"}
    assert len(fns) == 3


# ---------------------------------------------------------------------------
# 5. Timeout → stores status: unavailable
# ---------------------------------------------------------------------------

def test_timeout_stores_unavailable(monkeypatch):
    monkeypatch.setenv("AGENT_ENABLED", "true")
    monkeypatch.setenv("AGENT_TIMEOUT_S", "1")
    monkeypatch.setenv("AGENT_DAILY_CAP", "50")
    _reset_cap()

    import concurrent.futures

    def slow_run(*args, **kwargs):
        time.sleep(5)  # guaranteed to timeout with 1s cap
        return {"status": "ok"}

    stored = {}

    def fake_set_agent_review(eid, review):
        stored["review"] = review

    with patch("app.agent._run_agent", side_effect=slow_run), \
         patch("app.db.set_agent_review", side_effect=fake_set_agent_review):
        maybe_review(_ev())

    assert stored.get("review", {}).get("status") == "unavailable"


# ---------------------------------------------------------------------------
# 6. Invalid JSON output from agent → stores status: invalid
# ---------------------------------------------------------------------------

def test_invalid_json_output(monkeypatch):
    monkeypatch.setenv("AGENT_ENABLED", "true")
    monkeypatch.setenv("AGENT_DAILY_CAP", "50")
    _reset_cap()

    def bad_run(ev, eid, rules_priority):
        return {"status": "invalid", "created_at": time.time(), "model_id": "test-model"}

    stored = {}

    def fake_set_agent_review(eid, review):
        stored["review"] = review

    with patch("app.agent._run_agent", side_effect=bad_run), \
         patch("app.db.set_agent_review", side_effect=fake_set_agent_review):
        maybe_review(_ev())

    assert stored.get("review", {}).get("status") == "invalid"


# ---------------------------------------------------------------------------
# 7. AGENT_ENABLED=false → no agent_review field populated in the event dict
# ---------------------------------------------------------------------------

def test_agent_disabled_event_dict_unchanged(monkeypatch):
    """When disabled, the event dict must not be mutated."""
    monkeypatch.setenv("AGENT_ENABLED", "false")
    _reset_cap()

    ev = _ev()
    original_keys = set(ev.keys())

    with patch("app.db.set_agent_review"):
        maybe_review(ev)

    assert set(ev.keys()) == original_keys
    assert "agent_review" not in ev


# ---------------------------------------------------------------------------
# 8. Valid run → stores status: ok with all required fields
# ---------------------------------------------------------------------------

def test_valid_run_stores_ok(monkeypatch):
    monkeypatch.setenv("AGENT_ENABLED", "true")
    monkeypatch.setenv("AGENT_DAILY_CAP", "50")
    _reset_cap()

    good_result = {
        "agrees_with_rules": "agrees",
        "observations": [{"text": "Person standing normally", "evidence_ref": "person_detected"}],
        "possible_false_positive_reasons": ["routine activity"],
        "suggested_action": "No action needed.",
        "suggested_priority": "medium",
        "confidence": 0.85,
        "model_id": "anthropic.claude-3-haiku-20240307-v1:0",
        "status": "ok",
        "created_at": time.time(),
    }

    stored = {}

    def fake_set_agent_review(eid, review):
        stored["eid"] = eid
        stored["review"] = review

    with patch("app.agent._run_agent", return_value=good_result), \
         patch("app.db.set_agent_review", side_effect=fake_set_agent_review):
        maybe_review(_ev())

    review = stored.get("review", {})
    assert review.get("status") == "ok"
    required_fields = {
        "agrees_with_rules", "observations", "possible_false_positive_reasons",
        "suggested_action", "suggested_priority", "confidence", "model_id", "status", "created_at",
    }
    assert required_fields.issubset(review.keys())


# ---------------------------------------------------------------------------
# _validate_output unit tests
# ---------------------------------------------------------------------------

def test_validate_output_clamps_priority():
    raw = {
        "agrees_with_rules": "agrees",
        "observations": [{"text": "ok", "evidence_ref": "ref1"}],
        "possible_false_positive_reasons": [],
        "suggested_action": "watch",
        "suggested_priority": "low",  # should be clamped to high
        "confidence": 0.9,
        "model_id": "model-x",
    }
    result = _validate_output(raw, rules_priority="high")
    assert result["suggested_priority"] == "high"


def test_validate_output_drops_malformed_observations():
    raw = {
        "agrees_with_rules": "uncertain",
        "observations": [
            {"text": "valid obs", "evidence_ref": "ref_valid"},
            {"text": "missing evidence_ref"},           # malformed — no evidence_ref
            {"evidence_ref": "missing text field"},      # malformed — no text
            "not a dict",                                # totally wrong type
        ],
        "possible_false_positive_reasons": [],
        "suggested_action": "",
        "suggested_priority": "medium",
        "confidence": 0.5,
        "model_id": "",
    }
    result = _validate_output(raw, rules_priority="medium")
    assert len(result["observations"]) == 1
    assert result["observations"][0]["text"] == "valid obs"


def test_validate_output_rejects_non_dict():
    with pytest.raises(ValueError):
        _validate_output(["not", "a", "dict"], "low")


def test_validate_output_clamps_confidence():
    raw = {
        "agrees_with_rules": "agrees",
        "observations": [],
        "possible_false_positive_reasons": [],
        "suggested_action": "",
        "suggested_priority": "low",
        "confidence": 9999.0,  # should be clamped to 1.0
        "model_id": "",
    }
    result = _validate_output(raw, rules_priority="low")
    assert result["confidence"] == 1.0


# ---------------------------------------------------------------------------
# _is_eligible tests
# ---------------------------------------------------------------------------

def test_is_eligible_medium_priority():
    assert _is_eligible(_ev(priority="medium")) is True


def test_is_eligible_high_priority():
    assert _is_eligible(_ev(priority="high")) is True


def test_is_eligible_low_priority_no_indicators():
    assert _is_eligible(_ev(priority="low")) is False


def test_is_eligible_fall_possible():
    assert _is_eligible(_ev(priority="low", fall_level="possible")) is True


def test_is_eligible_fall_likely():
    assert _is_eligible(_ev(priority="low", fall_level="likely")) is True


def test_is_eligible_security_possible():
    assert _is_eligible(_ev(priority="low", sec_level="possible")) is True


# ---------------------------------------------------------------------------
# _cap_exceeded tests
# ---------------------------------------------------------------------------

def test_cap_not_exceeded(monkeypatch):
    monkeypatch.setenv("AGENT_DAILY_CAP", "10")
    _reset_cap()
    assert _cap_exceeded() is False


def test_cap_exceeded_at_limit(monkeypatch):
    monkeypatch.setenv("AGENT_DAILY_CAP", "2")
    _reset_cap()
    agent_module._cap_count = 2
    agent_module._cap_day = time.strftime("%Y-%m-%d")
    assert _cap_exceeded() is True
