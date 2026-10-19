import os
from .base import EventStore, DEFAULT_SETTINGS
from .sqlite_store import SqliteStore
from .dynamodb_store import DynamoDbStore


def get_store() -> EventStore:
    backend = os.getenv("STORAGE_BACKEND", "sqlite").lower()
    if backend == "dynamodb":
        return DynamoDbStore()
    return SqliteStore()


store: EventStore = get_store()

__all__ = ["EventStore", "SqliteStore", "DynamoDbStore", "get_store", "store", "DEFAULT_SETTINGS"]
