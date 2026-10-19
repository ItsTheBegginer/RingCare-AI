import hashlib
import uuid
from decimal import Decimal


def make_event_ids(ring_event_id: str | None = None) -> tuple[str, str]:
    """
    Returns (dynamo_pk, public_id)
    dynamo_pk: 'ring#<ring_event_id>' or 'sim#<uuid>'
    public_id: 'evt_<hash>'
    """
    if ring_event_id:
        pk = f"ring#{ring_event_id}"
        short_hash = hashlib.sha256(ring_event_id.encode("utf-8")).hexdigest()[:12]
        return pk, f"evt_{short_hash}"
    else:
        uid = uuid.uuid4().hex[:12]
        return f"sim#{uid}", f"evt_{uid}"


def to_decimal(obj):
    """Recursively convert Python float to Decimal for DynamoDB serialization."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_decimal(v) for v in obj]
    return obj


def from_decimal(obj):
    """Recursively convert Decimal back to float or int for JSON serialization."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, dict):
        return {k: from_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [from_decimal(v) for v in obj]
    return obj
