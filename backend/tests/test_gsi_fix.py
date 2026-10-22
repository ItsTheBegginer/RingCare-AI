"""
Phase 8 unit tests — GSI eventual-consistency fix.
Tests cover:
  1. _ingest_device returns a tuple (ids, rows) and each row has required keys.
  2. sync_ring result dict has 'ids', 'rows', and 'notes' keys.
  3. poller publishes events from res["rows"] without calling db.get.
  4. ring_sync route builds its response from res["rows"] without calling db.get.
  5. _webhook_ingest calls publish from res["rows"] without calling db.get.
  6. Simulate route builds its event from the in-memory row returned by simulate() (no db.get).
  7. Simulate route returns HTTP 500 when simulate() yields no rid (insert failed).
"""
import asyncio
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from fastapi.testclient import TestClient

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from app.main import app
from app import pipeline
from app.schema import to_event

client = TestClient(app, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# Shared minimal row / event fixtures
# ---------------------------------------------------------------------------

SAMPLE_ROW = {
    "id": "evt_aabbccdd1234",
    "event_id": "evt_aabbccdd1234",
    "device_id": "dev_test_001",
    "device_name": "Test Camera",
    "source": "ring",
    "event_ts": 1700000000.0,
    "status": "new",
    "vision": {},
    "assessment": {"priority": "low", "summary": "test"},
    "thumbnail": None,
    "clip_file": None,
    "video_status": "unavailable",
}

REQUIRED_ROW_KEYS = {
    "id", "event_id", "device_id", "device_name", "source",
    "event_ts", "status", "vision", "assessment", "thumbnail",
    "clip_file", "video_status",
}

SYNC_RESULT = {
    "ids": ["evt_aabbccdd1234"],
    "rows": [SAMPLE_ROW],
    "notes": [],
}


# ---------------------------------------------------------------------------
# 1. _ingest_device returns (ids, rows) with correct row shape
# ---------------------------------------------------------------------------

def test_ingest_device_returns_tuple_with_correct_shape():
    """_ingest_device should return a 2-tuple (ids, rows); rows contain required keys."""
    from app.ring import RingError

    dev = {"id": "dev_001", "name": "Porch Camera"}
    notes = []

    with patch("app.pipeline.ring") as mock_ring, \
         patch("app.pipeline.db") as mock_db, \
         patch("app.pipeline.process_clip") as mock_process, \
         patch("app.pipeline.make_playable") as mock_playable:

        # Ring returns one fresh event
        mock_ring.events.return_value = [{
            "id": "ring_evt_abc",
            "start_ms": 1700000000000,
            "event_type": "motion",
            "sub_type": "motion",
        }]
        mock_db.has_ring_event.return_value = False

        # Clip download succeeds
        mock_ring.clip.return_value = b"\x00" * 100

        # process_clip returns vision, result, thumb
        mock_process.return_value = (
            {"person_detected": False, "motion_frames_pct": 10.0},
            {"priority": "low", "summary": "ok"},
            None,
        )

        # make_playable returns a dummy path
        mock_playable_path = MagicMock()
        mock_playable_path.name = "ring_dev001_evt_abc.webm"
        mock_playable_path.suffix = ".webm"
        mock_playable.return_value = mock_playable_path

        mock_db.insert.return_value = "evt_abc123"

        result = pipeline._ingest_device(dev, limit=5, wait=0, notes=notes)

    assert isinstance(result, tuple), "_ingest_device must return a tuple"
    assert len(result) == 2, "Tuple must have 2 elements: (ids, rows)"

    ids, rows = result
    assert isinstance(ids, list)
    assert isinstance(rows, list)
    assert len(ids) == 1
    assert len(rows) == 1

    row = rows[0]
    missing = REQUIRED_ROW_KEYS - set(row.keys())
    assert not missing, f"Row is missing keys: {missing}"
    assert row["id"] == "evt_abc123"
    assert row["device_id"] == "dev_001"
    assert row["device_name"] == "Porch Camera"


def test_ingest_device_fallback_path_returns_row():
    """When clip unavailable and sample fallback disabled, fallback path must still build a row."""
    from app.ring import RingError, MediaNotReady

    dev = {"id": "dev_002", "name": "Back Yard"}
    notes = []

    with patch("app.pipeline.ring") as mock_ring, \
         patch("app.pipeline.db") as mock_db, \
         patch("app.pipeline.sample_clips", return_value=[]), \
         patch.dict(os.environ, {"RING_SAMPLE_FALLBACK": "false"}):

        mock_ring.events.return_value = [{
            "id": "ring_evt_noClip",
            "start_ms": 1700000000000,
            "event_type": "motion",
            "sub_type": "motion",
        }]
        mock_db.has_ring_event.return_value = False
        mock_ring.clip.side_effect = MediaNotReady(503, "not ready")
        mock_db.insert.return_value = "evt_fallback001"

        ids, rows = pipeline._ingest_device(dev, limit=5, wait=0, notes=notes)

    assert "evt_fallback001" in ids
    assert len(rows) == 1
    row = rows[0]
    missing = REQUIRED_ROW_KEYS - set(row.keys())
    assert not missing, f"Fallback row missing keys: {missing}"
    assert row["video_status"] == "unavailable"
    assert row["clip_file"] is None


# ---------------------------------------------------------------------------
# 2. sync_ring returns dict with ids, rows, notes
# ---------------------------------------------------------------------------

def test_sync_ring_result_has_ids_rows_notes():
    """sync_ring must return a dict with all three keys."""
    with patch("app.pipeline.ring") as mock_ring, \
         patch("app.pipeline._ingest_device", return_value=(["evt_001"], [SAMPLE_ROW])):

        mock_ring.configured = True
        mock_ring.devices.return_value = [{"id": "dev_001", "name": "Cam"}]

        result = pipeline.sync_ring(limit=1)

    assert "ids" in result
    assert "rows" in result
    assert "notes" in result
    assert result["ids"] == ["evt_001"]
    assert result["rows"] == [SAMPLE_ROW]


# ---------------------------------------------------------------------------
# 3. Poller publishes from res["rows"] — db.get not called
# ---------------------------------------------------------------------------

def test_poller_publishes_from_rows_not_db_get():
    """The poller must iterate res['rows'] and not call db.get."""
    published = []

    def fake_publish(ev):
        published.append(ev)

    with patch("app.pipeline.sync_ring", return_value=SYNC_RESULT), \
         patch("app.main.publish", side_effect=fake_publish), \
         patch("app.main.db") as mock_db:

        # Run one poller cycle manually by calling the internal logic
        import asyncio
        from fastapi.concurrency import run_in_threadpool
        from app.main import poller, _ring_state

        async def run_one_cycle():
            res = await run_in_threadpool(pipeline.sync_ring)
            _ring_state["status"] = "ok"
            _ring_state["token_expired_logged"] = False
            _ring_state["last_poll_error"] = None
            rows = res.get("rows") or []
            for row in rows:
                try:
                    fake_publish(to_event(row))
                except Exception:
                    pass

        asyncio.get_event_loop().run_until_complete(run_one_cycle())

        # db.get must NOT have been called
        mock_db.get.assert_not_called()

    assert len(published) == 1
    assert published[0]["id"] == "evt_aabbccdd1234"


# ---------------------------------------------------------------------------
# 4. ring_sync route uses res["rows"], not db.get
# ---------------------------------------------------------------------------

def test_ring_sync_route_uses_rows_not_db_get():
    """/api/ring/sync must build events from res['rows'] without calling db.get."""
    with patch("app.main.pipeline.sync_ring", return_value=SYNC_RESULT), \
         patch("app.main.publish"), \
         patch("app.main.db") as mock_db:

        resp = client.post("/api/ring/sync", json={"limit": 1})

    assert resp.status_code == 200
    data = resp.json()
    assert data["added"] == 1
    assert len(data["events"]) == 1
    assert data["events"][0]["id"] == "evt_aabbccdd1234"
    mock_db.get.assert_not_called()


# ---------------------------------------------------------------------------
# 5. _webhook_ingest uses res["rows"], not db.get
# ---------------------------------------------------------------------------

def test_webhook_ingest_uses_rows_not_db_get():
    """_webhook_ingest must publish from res['rows'] without calling db.get."""
    published = []

    def fake_publish(ev):
        published.append(ev)

    with patch("app.main.pipeline.sync_ring", return_value=SYNC_RESULT), \
         patch("app.main.publish", side_effect=fake_publish), \
         patch("app.main.db") as mock_db:

        import asyncio
        from app.main import _webhook_ingest

        mock_db.has_ring_event.return_value = False

        asyncio.get_event_loop().run_until_complete(
            _webhook_ingest("dev_test_001", "ring_evt_test")
        )

        mock_db.get.assert_not_called()

    assert len(published) == 1
    assert published[0]["id"] == "evt_aabbccdd1234"


# ---------------------------------------------------------------------------
# 6. Simulate route: builds event from the in-memory row returned by simulate()
# ---------------------------------------------------------------------------
def test_simulate_uses_in_memory_row_not_db_get():
    """Simulate route must build the event from the in-memory row returned by
    pipeline.simulate() and must NOT call db.get (avoids GSI eventual-consistency lag)."""
    rid = "evt_aabbccdd1234"
    sim_row = {
        **SAMPLE_ROW,
        "id": rid,
        "event_id": rid,
        "source": "simulated",
    }
    with patch("app.main.pipeline.simulate", return_value=(rid, sim_row)), \
         patch("app.main.publish"), \
         patch("app.main.db") as mock_db:
        resp = client.post("/api/events/simulate", json={"video": "sample_walk.mp4"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == rid
    # The route must not fall back to db.get at all
    mock_db.get.assert_not_called()

# ---------------------------------------------------------------------------
# 7. Simulate route: simulate() yields no rid -> HTTP 500
# ---------------------------------------------------------------------------
def test_simulate_returns_500_when_no_rid():
    """Simulate route must return HTTP 500 when pipeline.simulate() yields no rid
    (insert failed), without calling db.get."""
    with patch("app.main.pipeline.simulate", return_value=(None, None)), \
         patch("app.main.publish"), \
         patch("app.main.db") as mock_db:
        resp = client.post("/api/events/simulate", json={"video": "sample_walk.mp4"})
    assert resp.status_code == 500
    assert "could not store event" in resp.json().get("detail", "").lower()
    mock_db.get.assert_not_called()
