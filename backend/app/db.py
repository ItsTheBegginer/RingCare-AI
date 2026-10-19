"""Unified storage interface wrapper delegating to backend.app.storage.store."""
from .storage import store


def init():
    return store.init()


def insert(
    device_id,
    device_name,
    source,
    vision,
    assessment,
    thumbnail,
    event_ts=None,
    ring_event_id=None,
    clip_file=None,
    video_status=None,
    home_id="default",
):
    return store.insert(
        device_id=device_id,
        device_name=device_name,
        source=source,
        vision=vision,
        assessment=assessment,
        thumbnail=thumbnail,
        event_ts=event_ts,
        ring_event_id=ring_event_id,
        clip_file=clip_file,
        video_status=video_status,
        home_id=home_id,
    )


def get(eid):
    return store.get(str(eid))


def list_events(limit=100, home_id="default"):
    return store.list_events(limit=limit, home_id=home_id)


def has_ring_event(ring_event_id):
    return store.has_ring_event(ring_event_id)


def set_status(eid, status, note=None, actor="Primary Caregiver"):
    return store.set_status(str(eid), status, note=note, actor=actor)


def unacknowledged(limit=50, home_id="default"):
    return store.unacknowledged(limit=limit, home_id=home_id)


def mark_alerted(eid, expected_reminders, error=None):
    return store.mark_alerted(str(eid), expected_reminders, error=error)


def clear():
    return store.clear()


def get_settings(home_id="default"):
    return store.get_settings(home_id=home_id)


def put_settings(settings, home_id="default"):
    return store.put_settings(settings, home_id=home_id)


def set_agent_review(eid, review_dict):
    return store.set_agent_review(str(eid), review_dict)
