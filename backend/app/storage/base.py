from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

DEFAULT_SETTINGS: Dict[str, Any] = {
    "monitoringEnabled": True,
    "reviewNotificationsEnabled": True,
    "soundAlertsEnabled": True,
    "stationaryAlertThresholdSeconds": 15,
    "aiReviewSensitivity": "balanced",
    "cameraNightModeEnhance": True,
    "residentProfile": {
        "name": "Eleanor Vance",
        "residence": "Oakridge Assisted Living, Unit 304",
        "emergencyContact": "Sarah Vance (Daughter)",
        "emergencyPhone": "+1 (555) 019-2834",
        "notes": "Mild mobility impairment, uses walker occasionally. Prefers morning check-ins.",
    },
    "notificationRecipients": [],
}


class EventStore(ABC):
    @abstractmethod
    def init(self) -> None:
        """Initialize connections/tables if needed."""
        pass

    @abstractmethod
    def insert(
        self,
        device_id: str,
        device_name: str,
        source: str,
        vision: dict,
        assessment: dict,
        thumbnail: Optional[str],
        event_ts: Optional[float] = None,
        ring_event_id: Optional[str] = None,
        clip_file: Optional[str] = None,
        video_status: Optional[str] = None,
        home_id: str = "default",
    ) -> Optional[str]:
        """Insert a new event. Returns the public event id (e.g. 'evt_<hash>'), or None if already exists."""
        pass

    @abstractmethod
    def get(self, eid: str) -> Optional[dict]:
        """Fetch a single event by public id ('evt_<hash>') or storage pk."""
        pass

    @abstractmethod
    def list_events(self, limit: int = 200, home_id: str = "default") -> List[dict]:
        """List events ordered newest first."""
        pass

    @abstractmethod
    def has_ring_event(self, ring_event_id: str) -> bool:
        """Check if a Ring event id has already been ingested."""
        pass

    @abstractmethod
    def set_status(
        self,
        eid: str,
        status: str,
        note: Optional[str] = None,
        actor: str = "Primary Caregiver",
    ) -> bool:
        """Update caregiver review status ('acknowledged', 'dismissed')."""
        pass

    @abstractmethod
    def unacknowledged(self, limit: int = 50, home_id: str = "default") -> List[dict]:
        """Fetch events that require review and have not been acknowledged/dismissed."""
        pass

    @abstractmethod
    def mark_alerted(
        self,
        eid: str,
        expected_reminders: int,
        error: Optional[str] = None,
    ) -> bool:
        """Increment reminder counter and update last alert timestamp conditionally."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all events (used for development reset)."""
        pass

    @abstractmethod
    def get_settings(self, home_id: str = "default") -> dict:
        """Get caregiver settings for a home."""
        pass

    @abstractmethod
    def put_settings(self, settings: dict, home_id: str = "default") -> dict:
        """Save caregiver settings for a home."""
        pass

    @abstractmethod
    def set_agent_review(self, eid: str, review: dict) -> bool:
        """Store agent_review annotation on an event. Returns True on success."""
        pass
