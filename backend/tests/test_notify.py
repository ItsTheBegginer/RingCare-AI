import os
import time
from unittest.mock import MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from app.notify import (
    _format_subject,
    _format_body,
    extract_context,
    SnsNotifier,
    NtfyNotifier,
    CompositeNotifier,
    DISCLAIMER_GENERAL,
    DISCLAIMER_SECURITY,
)
from app.main import should_alert, _check_escalations


def test_format_subject_fall():
    ctx = {"fall_level": "possible", "category": "caretaking", "resident_name": "Eleanor"}
    subj = _format_subject(ctx, reminder_n=0)
    assert subj == "RingCare: possible fall - check now"

    # With reminder
    subj_rem = _format_subject(ctx, reminder_n=2)
    assert subj_rem == "RingCare: possible fall - check now (Reminder #2)"


def test_format_subject_security():
    ctx = {"fall_level": "none", "category": "security", "security_level": "possible", "resident_name": "Eleanor"}
    subj = _format_subject(ctx, reminder_n=0)
    assert subj == "RingCare: possible weapon or face covering seen - check now"

    subj_rem = _format_subject(ctx, reminder_n=1)
    assert subj_rem == "RingCare: possible weapon or face covering seen - check now (Reminder #1)"


def test_format_subject_caretaking():
    ctx = {"fall_level": "none", "category": "caretaking", "resident_name": "Eleanor Vance"}
    subj = _format_subject(ctx, reminder_n=0)
    assert subj == "RingCare: please check on Eleanor Vance"


def test_format_subject_length_clamp():
    # Long resident name clamped to <= 100 chars
    ctx = {"fall_level": "none", "category": "caretaking", "resident_name": "A" * 150}
    subj = _format_subject(ctx, reminder_n=1)
    assert len(subj) <= 100


def test_format_body_disclaimers():
    ctx_care = {
        "camera_name": "Living Room",
        "timestamp_str": "2026-10-19 12:00:00 UTC",
        "priority": "medium",
        "summary": "Motion with wide posture detected.",
        "recommended_action": "Check on resident.",
        "evidence": ["Person detected in 4 of 6 frames"],
        "category": "caretaking",
        "event_id": "evt_test_123",
    }
    body_care = _format_body(ctx_care)
    assert DISCLAIMER_GENERAL in body_care
    assert DISCLAIMER_SECURITY not in body_care
    assert "evt_test_123" in body_care

    ctx_sec = {**ctx_care, "category": "security", "security_level": "possible"}
    body_sec = _format_body(ctx_sec)
    assert DISCLAIMER_GENERAL in body_sec
    assert DISCLAIMER_SECURITY in body_sec


def test_sns_notifier_mock_publish():
    mock_sns = MagicMock()
    mock_sns.publish.return_value = {"MessageId": "msg-12345"}

    notifier = SnsNotifier(topic_arn="arn:aws:sns:ap-south-1:123456789012:ringcare-alerts", client=mock_sns)

    event = {
        "id": "evt_sample_01",
        "cameraName": "Backyard",
        "severity": "high",
        "category": "security",
        "securityIndicator": {"level": "possible"},
        "summary": "Possible weapon detected.",
        "recommendedAction": "Review footage.",
    }

    ok, err = notifier.send(event, reminder_n=0)
    assert ok is True
    assert err is None
    assert mock_sns.publish.called

    call_kwargs = mock_sns.publish.call_args[1]
    assert call_kwargs["TopicArn"] == "arn:aws:sns:ap-south-1:123456789012:ringcare-alerts"
    assert "possible weapon" in call_kwargs["Subject"]
    assert call_kwargs["MessageAttributes"]["severity"]["StringValue"] == "high"


def test_sns_notifier_missing_topic_arn():
    notifier = SnsNotifier(topic_arn="")
    ok, err = notifier.send({"id": "test"})
    assert ok is False
    assert "not configured" in err.lower()


def test_sns_notifier_client_error_retry():
    mock_sns = MagicMock()
    error_response = {"Error": {"Code": "InternalError", "Message": "SNS service busy"}}
    mock_sns.publish.side_effect = ClientError(error_response, "Publish")

    notifier = SnsNotifier(topic_arn="arn:aws:sns:ap-south-1:123456789012:ringcare-alerts", client=mock_sns)

    with patch("time.sleep"):  # Fast execution
        ok, err = notifier.send({"id": "test"})
    assert ok is False
    assert "InternalError" in err
    assert mock_sns.publish.call_count == 3  # Tried 3 times


def test_ntfy_notifier():
    notifier = NtfyNotifier(topic="test-topic")
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200

        event = {
            "id": "evt_sample_02",
            "cameraName": "Living Room",
            "severity": "medium",
            "category": "caretaking",
            "summary": "Prolonged inactivity detected.",
        }

        ok, err = notifier.send(event)
        assert ok is True
        assert err is None
        assert mock_post.called
        assert mock_post.call_args[1]["headers"]["Priority"] == "3"


def test_composite_notifier():
    mock_n1 = MagicMock()
    mock_n1.channel_name = "sns"
    mock_n1.send.return_value = (True, None)

    mock_n2 = MagicMock()
    mock_n2.channel_name = "ntfy"
    mock_n2.send.return_value = (False, "Network timeout")

    composite = CompositeNotifier([mock_n1, mock_n2])
    ok, msg = composite.send({"id": "evt_001"})

    assert ok is True
    assert "sns: ok" in msg
    assert "ntfy: failed" in msg


def test_escalation_policy_filtering():
    # Minimum priority = medium
    with patch.dict(os.environ, {"NOTIFY_MIN_PRIORITY": "medium"}):
        assert should_alert("low") is False
        assert should_alert("medium") is True
        assert should_alert("high") is True


def test_escalation_cycle_with_store():
    from app import db

    # Seed an unacknowledged event requiring review
    db.init()
    mock_event = {
        "event_id": "sim#esc_test_1",
        "id": "evt_esc_test_1",
        "home_id": "default",
        "device_id": "cam_esc",
        "device_name": "Hallway Cam",
        "status": "new",
        "reminders": 0,
        "event_ts": time.time() - 400,  # 6.6 min ago
        "last_alert_at": None,
        "assessment": {
            "priority": "high",
            "summary": "Possible fall detected on floor.",
            "category": "caretaking",
            "fall_indicator": {"level": "possible", "signals": ["Floor context"]},
        },
    }

    mock_notifier = MagicMock()
    mock_notifier.send.return_value = (True, None)

    with patch.dict(os.environ, {"ESCALATE_AFTER_MIN": "5", "MAX_REMINDERS": "3"}), \
         patch("app.main.get_notifier", return_value=mock_notifier), \
         patch.object(db, "unacknowledged", return_value=[mock_event]), \
         patch.object(db, "mark_alerted", return_value=True) as mock_mark:

        _check_escalations()

        assert mock_notifier.send.called
        # First send is reminder_n = 0
        call_args = mock_notifier.send.call_args
        assert call_args[1]["reminder_n"] == 0
        mock_mark.assert_called_with("sim#esc_test_1", expected_reminders=0, error=None)
