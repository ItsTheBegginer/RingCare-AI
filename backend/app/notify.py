"""Multi-channel notification subsystem for RingCare AI.
Provides Notifier interface with Amazon SNS as the primary alert channel,
plus optional ntfy and Telegram channels.
Supports category-specific subjects, structured evidence bodies,
mandatory honest medical/security disclaimers, and reminder tracking.
"""
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError
import requests

logger = logging.getLogger("ringcare.notify")

DISCLAIMER_GENERAL = (
    "This is a review prompt, not a confirmed emergency. "
    "If you think someone is in danger, call them or emergency services."
)

DISCLAIMER_SECURITY = (
    "Do not confront anyone. Call local emergency services if you believe there is a real threat."
)


def _format_subject(ctx: dict, reminder_n: int = 0) -> str:
    """Format category-specific subject (max 100 chars for AWS SNS)."""
    fall_level = ctx.get("fall_level", "none")
    category = ctx.get("category", "caretaking")
    sec_level = ctx.get("security_level", "none")
    resident = ctx.get("resident_name") or "resident"

    if fall_level in ("possible", "likely"):
        subj = "RingCare: possible fall - check now"
    elif category == "security" or sec_level == "possible":
        subj = "RingCare: possible weapon or face covering seen - check now"
    else:
        subj = f"RingCare: please check on {resident}"

    if reminder_n > 0:
        subj += f" (Reminder #{reminder_n})"

    # SNS requires Subject <= 100 characters
    return subj[:100]


def _format_body(ctx: dict, reminder_n: int = 0) -> str:
    """Format structured, evidence-based notification body."""
    lines = []

    if reminder_n > 0:
        lines.append(f"*** ESCALATION REMINDER #{reminder_n} ***")
        lines.append("This event requires review and has not yet been acknowledged.\n")

    lines.append(f"Camera: {ctx.get('camera_name', 'Ring Camera')}")
    lines.append(f"Time: {ctx.get('timestamp_str', 'Just now')}")
    lines.append(f"Review Priority: {str(ctx.get('priority', 'medium')).upper()}")

    summary = ctx.get("summary")
    if summary:
        lines.append(f"\nSummary:\n{summary}")

    evidence = ctx.get("evidence", [])
    if evidence:
        lines.append("\nObserved Evidence:")
        for ev in evidence[:6]:  # Keep top evidence points
            lines.append(f" - {ev}")

    action = ctx.get("recommended_action")
    if action:
        lines.append(f"\nRecommended Action:\n{action}")

    dash_url = ctx.get("dashboard_url", "http://localhost:3000")
    eid = ctx.get("event_id")
    event_link = f"{dash_url}/?event={eid}" if eid else dash_url
    lines.append(f"\nReview on Dashboard:\n{event_link}")

    lines.append("\n" + "-" * 40)
    lines.append(DISCLAIMER_GENERAL)

    if ctx.get("category") in ("security", "both") or ctx.get("security_level") == "possible":
        lines.append("\n" + DISCLAIMER_SECURITY)

    return "\n".join(lines)


def extract_context(event: dict, resident_name: str = "Eleanor Vance", dashboard_url: str = "http://localhost:3000") -> dict:
    """Normalize fields from either raw storage rows or frontend Event dicts."""
    # Priority / Severity
    prio = (
        event.get("severity")
        or event.get("aiAssessment", {}).get("urgency")
        or event.get("assessment", {}).get("priority")
        or "medium"
    ).lower()

    # Category
    cat = (
        event.get("category")
        or event.get("assessment", {}).get("category")
        or "caretaking"
    )

    # Fall Indicator
    fall_ind = event.get("fallIndicator") or event.get("assessment", {}).get("fall_indicator") or {}
    fall_level = fall_ind.get("level", "none")

    # Security Indicator
    sec_ind = event.get("securityIndicator") or event.get("assessment", {}).get("security_indicator") or {}
    sec_level = sec_ind.get("level", "none")

    # Camera & Time
    cam_name = event.get("cameraName") or event.get("device_name") or event.get("cameraId") or "Ring Camera"
    ts_val = event.get("event_ts") or event.get("timestamp")
    if isinstance(ts_val, (int, float)):
        ts_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts_val))
    elif isinstance(ts_val, str):
        ts_str = ts_val
    else:
        ts_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    # Summary & Action
    summary = (
        event.get("summary")
        or event.get("aiAssessment", {}).get("summary")
        or event.get("assessment", {}).get("summary")
        or ""
    )
    rec_action = (
        event.get("recommendedAction")
        or event.get("aiAssessment", {}).get("recommendedAction")
        or event.get("assessment", {}).get("recommended_action")
        or ""
    )

    # Evidence
    evidence = (
        event.get("aiAssessment", {}).get("evidence")
        or event.get("assessment", {}).get("observed_evidence")
        or []
    )

    eid = event.get("id") or event.get("event_id") or ""

    return {
        "event_id": eid,
        "priority": prio,
        "category": cat,
        "fall_level": fall_level,
        "security_level": sec_level,
        "camera_name": cam_name,
        "timestamp_str": ts_str,
        "summary": summary,
        "recommended_action": rec_action,
        "evidence": evidence,
        "resident_name": resident_name,
        "dashboard_url": dashboard_url,
    }


class Notifier(ABC):
    @abstractmethod
    def send(self, event: dict, reminder_n: int = 0) -> Tuple[bool, Optional[str]]:
        """Send notification. Returns (success, error_message)."""
        pass

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Name of the channel (e.g. 'sns', 'ntfy')."""
        pass


class SnsNotifier(Notifier):
    def __init__(self, topic_arn: Optional[str] = None, region_name: Optional[str] = None, client: Optional[Any] = None):
        self.topic_arn = os.getenv("SNS_TOPIC_ARN", "") if topic_arn is None else topic_arn
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-south-1")
        self._client = client

    @property
    def channel_name(self) -> str:
        return "sns"

    def _get_client(self):
        if self._client is not None:
            return self._client
        return boto3.client("sns", region_name=self.region_name)

    def send(self, event: dict, reminder_n: int = 0) -> Tuple[bool, Optional[str]]:
        if not self.topic_arn:
            msg = "SNS_TOPIC_ARN not configured; skipping SNS publish."
            logger.warning(msg)
            return False, msg

        ctx = extract_context(
            event,
            resident_name=os.getenv("RESIDENT_NAME", "Eleanor Vance"),
            dashboard_url=os.getenv("DASHBOARD_URL", "http://localhost:3000"),
        )
        subject = _format_subject(ctx, reminder_n)
        body = _format_body(ctx, reminder_n)
        severity = ctx.get("priority", "medium")

        client = self._get_client()
        attempts = 3
        last_err = None

        for attempt in range(1, attempts + 1):
            try:
                client.publish(
                    TopicArn=self.topic_arn,
                    Subject=subject,
                    Message=body,
                    MessageAttributes={
                        "severity": {"DataType": "String", "StringValue": severity},
                        "reminder": {"DataType": "Number", "StringValue": str(reminder_n)},
                    },
                )
                logger.info(f"SNS publish succeeded to {self.topic_arn} (subject: {subject})")
                return True, None
            except ClientError as e:
                err_code = e.response.get("Error", {}).get("Code", "Unknown")
                err_msg = e.response.get("Error", {}).get("Message", str(e))
                last_err = f"{err_code}: {err_msg}"
                logger.warning(f"SNS publish attempt {attempt}/{attempts} failed: {last_err}")
                if attempt < attempts:
                    time.sleep(0.5 * (2 ** (attempt - 1)))
            except Exception as e:
                last_err = str(e)
                logger.warning(f"SNS publish attempt {attempt}/{attempts} unexpected error: {last_err}")
                if attempt < attempts:
                    time.sleep(0.5 * (2 ** (attempt - 1)))

        return False, last_err


class NtfyNotifier(Notifier):
    def __init__(self, topic: Optional[str] = None, base_url: str = "https://ntfy.sh"):
        self.topic = topic or os.getenv("NTFY_TOPIC", "")
        self.base_url = os.getenv("NTFY_BASE_URL", base_url).rstrip("/")

    @property
    def channel_name(self) -> str:
        return "ntfy"

    def send(self, event: dict, reminder_n: int = 0) -> Tuple[bool, Optional[str]]:
        if not self.topic:
            return False, "NTFY_TOPIC not configured"

        ctx = extract_context(
            event,
            resident_name=os.getenv("RESIDENT_NAME", "Eleanor Vance"),
            dashboard_url=os.getenv("DASHBOARD_URL", "http://localhost:3000"),
        )
        subject = _format_subject(ctx, reminder_n)
        body = _format_body(ctx, reminder_n)
        prio = 4 if ctx.get("priority") == "high" else 3

        dash_url = ctx.get("dashboard_url", "http://localhost:3000")
        eid = ctx.get("event_id")
        click_url = f"{dash_url}/?event={eid}" if eid else dash_url

        url = f"{self.base_url}/{self.topic}"
        headers = {
            "Title": subject,
            "Priority": str(prio),
            "Tags": "warning,video_camera" if prio == 4 else "bell,video_camera",
            "Click": click_url,
        }

        try:
            resp = requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=5)
            if resp.status_code == 200:
                logger.info(f"Ntfy notification delivered to {self.topic}")
                return True, None
            return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
        except Exception as e:
            logger.warning(f"Ntfy notification failed: {e}")
            return False, str(e)


class TelegramNotifier(Notifier):
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")

    @property
    def channel_name(self) -> str:
        return "telegram"

    def send(self, event: dict, reminder_n: int = 0) -> Tuple[bool, Optional[str]]:
        if not self.bot_token or not self.chat_id:
            return False, "Telegram bot token or chat ID not configured"

        ctx = extract_context(
            event,
            resident_name=os.getenv("RESIDENT_NAME", "Eleanor Vance"),
            dashboard_url=os.getenv("DASHBOARD_URL", "http://localhost:3000"),
        )
        subject = _format_subject(ctx, reminder_n)
        body = _format_body(ctx, reminder_n)
        full_msg = f"<b>{subject}</b>\n\n{body}"

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": full_msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

        try:
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                return True, None
            return False, f"Telegram HTTP {resp.status_code}: {resp.text[:100]}"
        except Exception as e:
            return False, str(e)


class CompositeNotifier(Notifier):
    """Orchestrates dispatches to multiple channels based on NOTIFY_CHANNELS."""

    def __init__(self, notifiers: Optional[List[Notifier]] = None):
        self.notifiers: List[Notifier] = notifiers if notifiers is not None else []

    @property
    def channel_name(self) -> str:
        return "composite"

    def send(self, event: dict, reminder_n: int = 0) -> Tuple[bool, Optional[str]]:
        if not self.notifiers:
            return False, "No notification channels configured"

        results = []
        any_success = False

        for n in self.notifiers:
            try:
                ok, err = n.send(event, reminder_n=reminder_n)
                if ok:
                    any_success = True
                    results.append(f"{n.channel_name}: ok")
                else:
                    results.append(f"{n.channel_name}: failed ({err})")
            except Exception as e:
                results.append(f"{n.channel_name}: error ({e})")

        msg = "; ".join(results)
        return any_success, msg


def get_notifier() -> CompositeNotifier:
    """Build notifier from environment configuration."""
    channels = [c.strip().lower() for c in os.getenv("NOTIFY_CHANNELS", "sns,ntfy").split(",") if c.strip()]
    handlers: List[Notifier] = []

    for ch in channels:
        if ch == "sns":
            handlers.append(SnsNotifier())
        elif ch == "ntfy":
            handlers.append(NtfyNotifier())
        elif ch == "telegram":
            handlers.append(TelegramNotifier())

    return CompositeNotifier(handlers)
