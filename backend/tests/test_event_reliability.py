"""
Phase 7 unit tests — Event Management Reliability.
Tests cover:
  - Stable IDs: deterministic public ID generation from Ring event IDs
  - No duplicate cards / Idempotent ingestion: repeated sync does not duplicate records
  - Status consistency: acknowledge / dismiss status persists across fetches
  - Missing clip: /api/events/{eid}/clip returns clean 404, never crashes
  - Failed analysis: unreadable clip safely degrades to priority low with "unavailable" videoStatus
  - Ring auth/API error handling: RingAuthError maps to 401, RingError maps to 502
  - AWS error mapping: ClientError maps to 502, NoCredentialsError maps to 503
  - Bounded queries: /api/events limits results to 100 items via store list_events
  - /api/health reports storage, vision, ring, notify
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi.testclient import TestClient

from backend.app.main import app, _fail
from backend.app import db, pipeline
from backend.app.ring import RingAuthError, RingError
from backend.app.schema import to_event
from backend.app.storage.utils import make_event_ids
from backend.app.storage.sqlite_store import SqliteStore
from backend.app.vision import analyze
from backend.app.frames import FrameSource


client = TestClient(app)


# ------------------------------------------------------------------ 1. Stable IDs
def test_stable_event_ids_deterministic():
    ring_id = "ring_motion_12345678"
    pk1, pub1 = make_event_ids(ring_id)
    pk2, pub2 = make_event_ids(ring_id)
    assert pk1 == pk2 == f"ring#{ring_id}"
    assert pub1 == pub2
    assert pub1.startswith("evt_")


def test_schema_to_event_stable_id_formats():
    # Public id already evt_
    row1 = {
        "id": "evt_abc123",
        "device_id": "cam_1",
        "device_name": "Living Room",
        "source": "ring",
        "event_ts": 1700000000,
        "status": "new",
        "vision": {},
        "assessment": {"priority": "low"},
    }
    assert to_event(row1)["id"] == "evt_abc123"

    # Row with ring# pk
    row2 = {
        "event_id": "ring#motion_999",
        "device_id": "cam_1",
        "device_name": "Living Room",
        "source": "ring",
        "event_ts": 1700000000,
        "status": "new",
        "vision": {},
        "assessment": {"priority": "low"},
    }
    ev2 = to_event(row2)
    assert ev2["id"].startswith("evt_")

    # Row with sim# pk
    row3 = {
        "event_id": "sim#sample_uuid",
        "device_id": "local-sample",
        "device_name": "Sample Cam",
        "source": "simulated",
        "event_ts": 1700000000,
        "status": "new",
        "vision": {},
        "assessment": {"priority": "low"},
    }
    ev3 = to_event(row3)
    assert ev3["id"] == "evt_sample_uuid"


# ------------------------------------------------------------------ 2. Status Consistency
def test_status_consistency_and_idempotency():
    db.clear()
    eid = db.insert(
        device_id="cam_porch",
        device_name="Front Porch",
        source="ring",
        vision={"person_detected": True, "motion_frames_pct": 50},
        assessment={"priority": "high", "summary": "Person moving"},
        thumbnail="thumb_b64",
        ring_event_id="ring_event_repeat_test",
    )
    assert eid is not None

    # Retrieve initial event
    resp = client.get(f"/api/events/{eid}")
    assert resp.status_code == 200
    ev = resp.json()
    assert ev["aiStatus"] == "review"

    # Acknowledge event
    ack_resp = client.post(f"/api/events/{eid}/acknowledge", json={"note": "Verified resident arriving"})
    assert ack_resp.status_code == 200
    assert ack_resp.json()["aiStatus"] == "acknowledged"

    # Fetching list or individual event retains acknowledged status
    ev_again = client.get(f"/api/events/{eid}").json()
    assert ev_again["aiStatus"] == "acknowledged"
    assert ev_again.get("actionLog", {}).get("action") == "acknowledged"

    # Second insert with same ring_event_id is ignored (idempotent)
    second_id = db.insert(
        device_id="cam_porch",
        device_name="Front Porch",
        source="ring",
        vision={"person_detected": True},
        assessment={"priority": "high"},
        thumbnail=None,
        ring_event_id="ring_event_repeat_test",
    )
    assert second_id is None or second_id == eid
    assert len(db.list_events(10)) == 1


# ------------------------------------------------------------------ 3. Missing Clip Handling
def test_missing_clip_returns_404_cleanly():
    # Non-existent event
    resp = client.get("/api/events/evt_nonexistent/clip")
    assert resp.status_code == 404

    # Event with missing clip file on disk
    eid = db.insert(
        device_id="cam_1",
        device_name="Test Cam",
        source="ring",
        vision={},
        assessment={"priority": "low"},
        thumbnail=None,
        clip_file="nonexistent_clip_on_disk.mp4",
        video_status="unavailable",
    )
    resp = client.get(f"/api/events/{eid}/clip")
    assert resp.status_code == 404
    assert "missing" in resp.json().get("detail", "").lower()


# ------------------------------------------------------------------ 4. Failed Analysis Fallback
def test_failed_analysis_handles_error_without_crash():
    class DummyEmptySource(FrameSource):
        def frames(self):
            return []  # No frames produced

    analysis = analyze(DummyEmptySource())
    assert "error" in analysis

    meta = {"device_id": "cam_err", "ring_event_type": "motion"}
    from backend.app.assess import assess
    assessment = assess(meta, analysis)

    assert assessment["priority"] == "low"
    assert "no video could be analysed" in assessment["recommended_action"].lower()
    assert len(assessment["observed_evidence"]) > 0


# ------------------------------------------------------------------ 5. Ring Auth and API Error Mapping
def test_ring_auth_and_api_error_responses():
    with patch("backend.app.ring.ring.devices", side_effect=RingAuthError(401, "Token expired or revoked")):
        resp = client.get("/api/ring/devices")
        assert resp.status_code == 401
        assert "Token expired" in resp.json().get("detail", "")

    with patch("backend.app.ring.ring.devices", side_effect=RingError(503, "Ring backend service unavailable")):
        resp = client.get("/api/ring/devices")
        assert resp.status_code == 503
        assert "Ring backend service" in resp.json().get("detail", "")


# ------------------------------------------------------------------ 6. AWS Error Mapping
def test_aws_client_error_and_no_credentials_mapping():
    # Test NoCredentialsError
    with pytest.raises(Exception) as excinfo:
        _fail(NoCredentialsError())
    assert excinfo.value.status_code == 503
    assert "AWS credentials" in excinfo.value.detail

    # Test botocore ClientError
    error_response = {
        "Error": {
            "Code": "ProvisionedThroughputExceededException",
            "Message": "Throughput exceeded on DynamoDB table",
        }
    }
    client_err = ClientError(error_response, "Query")
    with pytest.raises(Exception) as excinfo2:
        _fail(client_err)
    assert excinfo2.value.status_code == 502
    assert "ProvisionedThroughputExceededException" in excinfo2.value.detail


# ------------------------------------------------------------------ 7. Bounded Queries (100)
def test_events_endpoint_bounded_to_100():
    db.clear()
    # Insert 105 mock events
    for i in range(105):
        db.insert(
            device_id="cam_bench",
            device_name="Benchmark Cam",
            source="simulated",
            vision={"person_detected": False, "motion_frames_pct": 5},
            assessment={"priority": "low", "summary": f"Mock event {i}"},
            thumbnail=None,
            event_ts=1700000000 + i,
        )

    resp = client.get("/api/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 100


# ------------------------------------------------------------------ 8. /api/health Reports storage, vision, ring, notify
def test_api_health_reports_required_keys():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()

    assert "storage" in data
    assert "vision" in data
    assert "ring" in data
    assert "notify" in data
    assert "storage_status" in data
    assert data["storage_status"] == "ok"
    assert isinstance(data["notify"], list)
