import logging
import os
import time
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
from .base import DEFAULT_SETTINGS, EventStore
from .utils import from_decimal, make_event_ids, to_decimal
logger = logging.getLogger("ringcare.storage.dynamodb")
class DynamoDbStore(EventStore):
    def __init__(
        self,
        events_table_name: Optional[str] = None,
        settings_table_name: Optional[str] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        self.events_table_name = events_table_name or os.getenv("DDB_EVENTS_TABLE", "RingCareEvents")
        self.settings_table_name = settings_table_name or os.getenv("DDB_SETTINGS_TABLE", "RingCareSettings")
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-south-1")
        self.endpoint_url = endpoint_url or os.getenv("DDB_ENDPOINT") or None
        self._resource = None
        self._events_table = None
        self._settings_table = None
    def _get_resource(self):
        if self._resource is None:
            kwargs = {"region_name": self.region_name}
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            self._resource = boto3.resource("dynamodb", **kwargs)
            self._events_table = self._resource.Table(self.events_table_name)
            self._settings_table = self._resource.Table(self.settings_table_name)
        return self._resource
    @property
    def events_table(self):
        self._get_resource()
        return self._events_table
    @property
    def settings_table(self):
        self._get_resource()
        return self._settings_table
    def init(self) -> None:
        """Verify tables are accessible."""
        try:
            self._get_resource()
            self.events_table.load()
            self.settings_table.load()
        except Exception as e:
            logger.warning(f"DynamoDB tables not immediately accessible: {e}")
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
        # Filter keyframes out of vision map for storage efficiency
        vision_clean = {k: v for k, v in vision.items() if k != "keyframes"}
        now = time.time()
        ts = event_ts if event_ts is not None else now
        pk, public_id = make_event_ids(ring_event_id)
        # Default video_status if not explicitly provided
        if not video_status:
            if source in ("simulated", "ring+sample-clip"):
                video_status = "sample"
            elif clip_file:
                video_status = "converted" if ".play." in clip_file or clip_file.endswith(".webm") else "ring_clip"
            else:
                video_status = "unavailable"
        # Safe thumbnail clamp: ensure thumbnail does not exceed 60 KB
        thumb_safe = thumbnail
        if thumb_safe and len(thumb_safe) > 80000:
            thumb_safe = None
        item = {
            "event_id": pk,
            "id": public_id,
            "home_id": home_id,
            "device_id": device_id,
            "device_name": device_name,
            "source": source,
            "created_at": to_decimal(now),
            "event_ts": to_decimal(ts),
            "video_status": video_status,
            "vision": to_decimal(vision_clean),
            "assessment": to_decimal(assessment),
            "status": "new",
            "reminders": 0,
        }
        if ring_event_id:
            item["ring_event_id"] = ring_event_id
        if clip_file:
            item["clip_file"] = clip_file
        if thumb_safe:
            item["thumbnail"] = thumb_safe
        try:
            self.events_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(event_id)",
            )
            return public_id
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                # Already stored - idempotent ingestion
                logger.info(f"Event {pk} already exists in DynamoDB; ignoring duplicate.")
                return None
            logger.error(f"Failed to put item into DynamoDB: {e}")
            raise
    def _resolve_pk(self, eid: str) -> Optional[str]:
        """Resolve a public id (evt_<hash>) or PK to its DynamoDB partition key."""
        clean = str(eid).strip()
        if clean.startswith("ring#") or clean.startswith("sim#"):
            return clean
        # Query GSI by-public-id if configured, or query by-home-time and match id
        try:
            resp = self.events_table.query(
                IndexName="by-public-id",
                KeyConditionExpression="#id = :eid",
                ExpressionAttributeNames={"#id": "id"},
                ExpressionAttributeValues={":eid": clean},
                Limit=1,
            )
            items = resp.get("Items", [])
            if items:
                return items[0]["event_id"]
        except Exception:
            pass
        # Fallback: query newest events from by-home-time GSI
        try:
            resp = self.events_table.query(
                IndexName="by-home-time",
                KeyConditionExpression="home_id = :h",
                ExpressionAttributeValues={":h": "default"},
                ScanIndexForward=False,
                Limit=100,
            )
            for it in resp.get("Items", []):
                if it.get("id") == clean or it.get("event_id") == clean:
                    return it["event_id"]
        except Exception as e:
            logger.warning(f"Error resolving pk for {clean}: {e}")
        return None
    def get(self, eid: str) -> Optional[dict]:
        clean = str(eid).strip()
        pk = clean if (clean.startswith("ring#") or clean.startswith("sim#")) else self._resolve_pk(clean)
        if not pk:
            return None
        try:
            resp = self.events_table.get_item(Key={"event_id": pk})
            item = resp.get("Item")
            return from_decimal(item) if item else None
        except Exception as e:
            logger.error(f"Failed to get event {eid} from DynamoDB: {e}")
            return None
    def list_events(self, limit: int = 100, home_id: str = "default") -> List[dict]:
        """Fetch newest events using GSI by-home-time with Query (never Scan)."""
        try:
            resp = self.events_table.query(
                IndexName="by-home-time",
                KeyConditionExpression="home_id = :h",
                ExpressionAttributeValues={":h": home_id},
                ScanIndexForward=False,
                Limit=limit,
            )
            return [from_decimal(item) for item in resp.get("Items", [])]
        except Exception as e:
            logger.error(f"Failed to query events from DynamoDB GSI: {e}")
            return []
    def has_ring_event(self, ring_event_id: str) -> bool:
        if not ring_event_id:
            return False
        pk = f"ring#{ring_event_id}"
        try:
            resp = self.events_table.get_item(
                Key={"event_id": pk},
                ProjectionExpression="event_id",
            )
            return "Item" in resp
        except Exception as e:
            logger.error(f"Failed to check has_ring_event in DynamoDB: {e}")
            return False
    def set_status(
        self,
        eid: str,
        status: str,
        note: Optional[str] = None,
        actor: str = "Primary Caregiver",
    ) -> bool:
        pk = self._resolve_pk(eid) if not (str(eid).startswith("ring#") or str(eid).startswith("sim#")) else str(eid)
        if not pk:
            return False
        now = to_decimal(time.time())
        try:
            self.events_table.update_item(
                Key={"event_id": pk},
                UpdateExpression="SET #s = :status, note = :note, acted_at = :acted_at, actor = :actor",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":status": status,
                    ":note": note or "",
                    ":acted_at": now,
                    ":actor": actor or "Primary Caregiver",
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update status in DynamoDB for {eid}: {e}")
            return False
    def unacknowledged(self, limit: int = 50, home_id: str = "default") -> List[dict]:
        """Fetch unacknowledged events using GSI by-status-time."""
        try:
            resp = self.events_table.query(
                IndexName="by-status-time",
                KeyConditionExpression="#s = :status",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":status": "new"},
                ScanIndexForward=True,
                Limit=limit,
            )
            items = [from_decimal(it) for it in resp.get("Items", [])]
            return [it for it in items if it.get("home_id", "default") == home_id]
        except Exception as e:
            logger.error(f"Failed to query unacknowledged events from DynamoDB GSI: {e}")
            return []
    def mark_alerted(
        self,
        eid: str,
        expected_reminders: int,
        error: Optional[str] = None,
    ) -> bool:
        pk = self._resolve_pk(eid) if not (str(eid).startswith("ring#") or str(eid).startswith("sim#")) else str(eid)
        if not pk:
            return False
        now = to_decimal(time.time())
        try:
            self.events_table.update_item(
                Key={"event_id": pk},
                UpdateExpression="SET reminders = reminders + :one, last_alert_at = :now, last_alert_error = :err",
                ConditionExpression="#s = :expected_status AND (attribute_not_exists(reminders) OR reminders = :exp_rem)",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":expected_status": "new",
                    ":exp_rem": expected_reminders,
                    ":one": 1,
                    ":now": now,
                    ":err": error or "",
                },
            )
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                logger.info(f"Condition check failed when marking {pk} alerted (already acted upon or reminder race).")
                return False
            logger.error(f"Error marking alerted in DynamoDB: {e}")
            return False
    def clear(self) -> None:
        """Scan and delete all items (for dev reset only).
        Uses individual DeleteItem calls (covered by the least-privilege IAM policy)
        rather than batch_writer which requires BatchWriteItem permission.
        """
        try:
            # Paginate in case there are more than 1 MB of keys
            last_key = None
            while True:
                kwargs: dict = {"ProjectionExpression": "event_id"}
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key
                resp = self.events_table.scan(**kwargs)
                for item in resp.get("Items", []):
                    self.events_table.delete_item(Key={"event_id": item["event_id"]})
                last_key = resp.get("LastEvaluatedKey")
                if not last_key:
                    break
        except Exception as e:
            logger.error(f"Error clearing DynamoDB events: {e}")
    def get_settings(self, home_id: str = "default") -> dict:
        try:
            resp = self.settings_table.get_item(Key={"home_id": home_id})
            item = resp.get("Item")
            if item and "settings" in item:
                return from_decimal(item["settings"])
        except Exception as e:
            logger.warning(f"Failed to fetch settings from DynamoDB: {e}")
        return dict(DEFAULT_SETTINGS)
    def put_settings(self, settings: dict, home_id: str = "default") -> dict:
        try:
            self.settings_table.put_item(
                Item={
                    "home_id": home_id,
                    "settings": to_decimal(settings),
                    "updated_at": to_decimal(time.time()),
                }
            )
        except Exception as e:
            logger.error(f"Failed to save settings to DynamoDB: {e}")
            raise
        return settings
