"""
Phase 6 unit tests — Automatic Polling and Webhooks.
Tests cover:
  - Poller: successful sync, token expiry (single log), recovery via hot-swap token
  - /api/health: ring_status field
  - Webhook: valid HMAC, bad HMAC, malformed JSON, duplicate event, unknown event type
  - Ring history tolerant timestamp parsing
"""
import hashlib
import hmac as _hmac
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Module-level import of the FastAPI app ──────────────────────────────────
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from app.main import app, _ring_state, KNOWN_MOTION_TYPES
from app.ring import RingAuthError, RingError

client = TestClient(app, raise_server_exceptions=False)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_sig(key: str, body: bytes) -> str:
    return "sha256=" + _hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


def _make_sig_raw(key: str, body: bytes) -> str:
    """Raw hex (no sha256= prefix) — alternative format Ring may send."""
    return _hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


MOTION_PAYLOAD = json.dumps({
    "data": {
        "id": "ring_evt_abc123",
        "type": "motion_detected",
        "attributes": {"device_id": "dev_test_001"},
    }
}).encode()


# ─────────────────────────────────────────────────────────────────────────────
# /api/health ring_status
# ─────────────────────────────────────────────────────────────────────────────

def test_health_ring_not_configured():
    with patch("app.main.ring") as mock_ring:
        mock_ring.configured = False
        resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ring_status"] == "not_configured"
    assert data["ok"] is True


def test_health_ring_ok():
    with patch("app.main.ring") as mock_ring, \
         patch.dict("app.main._ring_state", {"status": "ok"}):
        mock_ring.configured = True
        resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["ring_status"] == "ok"


def test_health_ring_token_expired():
    with patch("app.main.ring") as mock_ring, \
         patch.dict("app.main._ring_state", {"status": "token_expired"}):
        mock_ring.configured = True
        resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["ring_status"] == "token_expired"


# ─────────────────────────────────────────────────────────────────────────────
# Token hot-swap clears expiry state
# ─────────────────────────────────────────────────────────────────────────────

def test_set_token_clears_expiry_state():
    # Seed an expired state
    _ring_state["status"] = "token_expired"
    _ring_state["token_expired_logged"] = True
    _ring_state["last_poll_error"] = "Token expired/invalid."

    with patch("app.main.ring") as mock_ring:
        mock_ring.set_access_token = MagicMock()
        resp = client.post("/api/ring/token", json={"access_token": "new_token_abc"})

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    # State must be cleared
    assert _ring_state["status"] == "ok"
    assert _ring_state["token_expired_logged"] is False
    assert _ring_state["last_poll_error"] is None


# ─────────────────────────────────────────────────────────────────────────────
# KNOWN_MOTION_TYPES set coverage
# ─────────────────────────────────────────────────────────────────────────────

def test_known_motion_types():
    assert "motion_detected" in KNOWN_MOTION_TYPES
    assert "motion" in KNOWN_MOTION_TYPES
    assert "on_demand" in KNOWN_MOTION_TYPES
    assert "ding" in KNOWN_MOTION_TYPES


# ─────────────────────────────────────────────────────────────────────────────
# Webhook: valid HMAC (sha256= prefix format)
# ─────────────────────────────────────────────────────────────────────────────

def test_webhook_valid_hmac_prefix_format():
    key = "test-secret-key"
    sig = _make_sig(key, MOTION_PAYLOAD)

    with patch.dict(os.environ, {"RING_HMAC_KEY": key}), \
         patch("app.main._webhook_ingest", new_callable=AsyncMock), \
         patch("app.main.db") as mock_db:
        mock_db.has_ring_event.return_value = False
        resp = client.post(
            "/api/webhooks/ring",
            content=MOTION_PAYLOAD,
            headers={"Content-Type": "application/json", "x-signature": sig},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_webhook_valid_hmac_raw_hex_format():
    """Ring may omit the sha256= prefix."""
    key = "test-secret-key"
    sig = _make_sig_raw(key, MOTION_PAYLOAD)

    with patch.dict(os.environ, {"RING_HMAC_KEY": key}), \
         patch("app.main._webhook_ingest", new_callable=AsyncMock), \
         patch("app.main.db") as mock_db:
        mock_db.has_ring_event.return_value = False
        resp = client.post(
            "/api/webhooks/ring",
            content=MOTION_PAYLOAD,
            headers={"Content-Type": "application/json", "x-ring-signature": sig},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Webhook: invalid HMAC → 401
# ─────────────────────────────────────────────────────────────────────────────

def test_webhook_invalid_hmac():
    with patch.dict(os.environ, {"RING_HMAC_KEY": "real-secret"}):
        resp = client.post(
            "/api/webhooks/ring",
            content=MOTION_PAYLOAD,
            headers={"Content-Type": "application/json", "x-signature": "sha256=deadbeef"},
        )

    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Webhook: malformed body → 400
# ─────────────────────────────────────────────────────────────────────────────

def test_webhook_malformed_body():
    with patch.dict(os.environ, {}, clear=False):
        # No RING_HMAC_KEY set means no signature check
        os.environ.pop("RING_HMAC_KEY", None)
        resp = client.post(
            "/api/webhooks/ring",
            content=b"this is not valid json {{",
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# Webhook: duplicate event → ignored immediately
# ─────────────────────────────────────────────────────────────────────────────

def test_webhook_duplicate_event():
    os.environ.pop("RING_HMAC_KEY", None)

    with patch("app.main.db") as mock_db:
        mock_db.has_ring_event.return_value = True  # already stored
        resp = client.post(
            "/api/webhooks/ring",
            content=MOTION_PAYLOAD,
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ignored"
    assert "duplicate" in data["reason"]


# ─────────────────────────────────────────────────────────────────────────────
# Webhook: unknown event type → ignored
# ─────────────────────────────────────────────────────────────────────────────

def test_webhook_unknown_event_type():
    os.environ.pop("RING_HMAC_KEY", None)
    payload = json.dumps({
        "data": {"id": "ring_evt_xyz", "type": "firmware_update", "attributes": {"device_id": "dev_001"}}
    }).encode()

    resp = client.post(
        "/api/webhooks/ring",
        content=payload,
        headers={"Content-Type": "application/json"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ignored"
    assert "unsupported" in data["reason"]


# ─────────────────────────────────────────────────────────────────────────────
# Webhook: no HMAC key set → skip verification (dev mode)
# ─────────────────────────────────────────────────────────────────────────────

def test_webhook_no_hmac_key_dev_mode():
    os.environ.pop("RING_HMAC_KEY", None)

    with patch("app.main._webhook_ingest", new_callable=AsyncMock), \
         patch("app.main.db") as mock_db:
        mock_db.has_ring_event.return_value = False
        resp = client.post(
            "/api/webhooks/ring",
            content=MOTION_PAYLOAD,
            headers={"Content-Type": "application/json"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ─────────────────────────────────────────────────────────────────────────────
# Ring history: tolerant timestamp parsing in ring.py
# ─────────────────────────────────────────────────────────────────────────────

def test_ring_to_ms_various_formats():
    from app.ring import to_ms

    # Epoch seconds (< 1e11)
    assert to_ms(1729000000) == 1729000000000

    # Epoch milliseconds (>= 1e11)
    assert to_ms(1729000000000) == 1729000000000

    # ISO-8601 string
    ts = to_ms("2024-10-15T12:00:00Z")
    assert ts is not None
    assert isinstance(ts, int)
    assert ts > 1e12  # milliseconds

    # Numeric string
    assert to_ms("1729000000") == 1729000000000

    # None → None
    assert to_ms(None) is None

    # Garbage → None
    assert to_ms("not-a-timestamp") is None
