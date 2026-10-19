import os
import time
import pytest
import boto3
from moto import mock_aws

from app.storage.base import DEFAULT_SETTINGS
from app.storage.sqlite_store import SqliteStore
from app.storage.dynamodb_store import DynamoDbStore
from app.storage.utils import make_event_ids, to_decimal, from_decimal


def test_utils_make_event_ids():
    pk1, pub1 = make_event_ids("ring-12345")
    assert pk1 == "ring#ring-12345"
    assert pub1.startswith("evt_")

    pk2, pub2 = make_event_ids("ring-12345")
    assert pk1 == pk2
    assert pub1 == pub2  # deterministic for ring events

    pk_sim, pub_sim = make_event_ids(None)
    assert pk_sim.startswith("sim#")
    assert pub_sim.startswith("evt_")


def test_utils_decimal_conversion():
    data = {
        "score": 0.95,
        "nested": {"val": 1.25, "int": 10},
        "list": [0.1, 0.2, 5],
        "str": "hello",
    }
    dec = to_decimal(data)
    from decimal import Decimal
    assert isinstance(dec["score"], Decimal)
    assert isinstance(dec["nested"]["val"], Decimal)

    recovered = from_decimal(dec)
    assert recovered["score"] == 0.95
    assert recovered["nested"]["int"] == 10
    assert recovered["list"] == [0.1, 0.2, 5]


def test_sqlite_store(tmp_path):
    db_file = str(tmp_path / "test.db")
    store = SqliteStore(db_file)
    store.init()

    # 1. Insert event
    vision = {"person_detected": True, "motion_frames_pct": 30.0}
    assessment = {"priority": "medium", "summary": "Person moving"}
    eid = store.insert(
        device_id="cam_1",
        device_name="Front Door",
        source="ring",
        vision=vision,
        assessment=assessment,
        thumbnail="base64thumb",
        event_ts=time.time(),
        ring_event_id="ring_abc1",
        clip_file="clip1.mp4",
        video_status="ring_clip",
    )
    assert eid is not None
    assert eid.startswith("evt_")

    # 2. Idempotent insert: second attempt with same ring_event_id returns None
    eid2 = store.insert(
        device_id="cam_1",
        device_name="Front Door",
        source="ring",
        vision=vision,
        assessment=assessment,
        thumbnail="base64thumb",
        event_ts=time.time(),
        ring_event_id="ring_abc1",
    )
    assert eid2 is None

    # 3. Get event
    ev = store.get(eid)
    assert ev is not None
    assert ev["device_name"] == "Front Door"
    assert ev["status"] == "new"
    assert ev["video_status"] == "ring_clip"
    assert ev["vision"]["person_detected"] is True

    # 4. Update status
    ok = store.set_status(eid, "acknowledged", note="Checked by nurse")
    assert ok is True
    ev_updated = store.get(eid)
    assert ev_updated["status"] == "acknowledged"
    assert ev_updated["note"] == "Checked by nurse"

    # 5. List events
    events = store.list_events()
    assert len(events) == 1

    # 6. Settings
    settings = store.get_settings()
    assert "monitoringEnabled" in settings
    settings["monitoringEnabled"] = False
    store.put_settings(settings)
    assert store.get_settings()["monitoringEnabled"] is False


@mock_aws
def test_dynamodb_store():
    # Setup mock DynamoDB tables
    ddb = boto3.resource("dynamodb", region_name="ap-south-1")
    events_table = ddb.create_table(
        TableName="RingCareEventsTest",
        KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "event_id", "AttributeType": "S"},
            {"AttributeName": "home_id", "AttributeType": "S"},
            {"AttributeName": "event_ts", "AttributeType": "N"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "id", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "by-home-time",
                "KeySchema": [
                    {"AttributeName": "home_id", "KeyType": "HASH"},
                    {"AttributeName": "event_ts", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "by-status-time",
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "event_ts", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "by-public-id",
                "KeySchema": [
                    {"AttributeName": "id", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    events_table.wait_until_exists()

    settings_table = ddb.create_table(
        TableName="RingCareSettingsTest",
        KeySchema=[{"AttributeName": "home_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "home_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    settings_table.wait_until_exists()

    store = DynamoDbStore(
        events_table_name="RingCareEventsTest",
        settings_table_name="RingCareSettingsTest",
        region_name="ap-south-1",
    )

    # 1. Insert event
    vision = {"person_detected": True, "motion_peak": 0.42}
    assessment = {"priority": "high", "summary": "Stationary posture detected"}
    ts = time.time()
    eid = store.insert(
        device_id="cam_living_room",
        device_name="Living Room",
        source="ring",
        vision=vision,
        assessment=assessment,
        thumbnail="base64thumb",
        event_ts=ts,
        ring_event_id="ring_event_999",
        clip_file="clip999.webm",
        video_status="converted",
    )
    assert eid is not None
    assert eid.startswith("evt_")

    # 2. Idempotent insert: duplicate conditional check fails gracefully and returns None
    dup = store.insert(
        device_id="cam_living_room",
        device_name="Living Room",
        source="ring",
        vision=vision,
        assessment=assessment,
        thumbnail="base64thumb",
        event_ts=ts,
        ring_event_id="ring_event_999",
    )
    assert dup is None

    # 3. Fetch event by public id
    ev = store.get(eid)
    assert ev is not None
    assert ev["device_name"] == "Living Room"
    assert ev["status"] == "new"
    assert ev["video_status"] == "converted"
    assert ev["vision"]["motion_peak"] == 0.42

    # 4. Check has_ring_event
    assert store.has_ring_event("ring_event_999") is True
    assert store.has_ring_event("non_existent") is False

    # 5. Query via GSI by-home-time (list_events)
    events = store.list_events()
    assert len(events) == 1
    assert events[0]["id"] == eid

    # 6. Unacknowledged query via GSI by-status-time
    unack = store.unacknowledged()
    assert len(unack) == 1
    assert unack[0]["id"] == eid

    # 7. Acknowledge event
    ok = store.set_status(eid, "acknowledged", note="Resident is okay")
    assert ok is True
    assert store.get(eid)["status"] == "acknowledged"

    # Unacknowledged should now be empty
    assert len(store.unacknowledged()) == 0

    # 8. Settings in DynamoDB
    s = store.get_settings()
    assert s["monitoringEnabled"] is True
    s["residentProfile"]["name"] = "Alice Smith"
    store.put_settings(s)

    reloaded = store.get_settings()
    assert reloaded["residentProfile"]["name"] == "Alice Smith"
