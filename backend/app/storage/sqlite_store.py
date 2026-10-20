import json
import sqlite3
import time
from typing import Any, Dict, List, Optional
from .base import DEFAULT_SETTINGS, EventStore
from .utils import make_event_ids
DB_FILE = "ringcare_v2.db"
class SqliteStore(EventStore):
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
    def _c(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c
    def init(self) -> None:
        with self._c() as c:
            # Events table (supports both string IDs and legacy integer rows)
            c.execute("""CREATE TABLE IF NOT EXISTS events(
                id TEXT PRIMARY KEY,
                event_id TEXT UNIQUE,
                home_id TEXT DEFAULT 'default',
                device_id TEXT,
                device_name TEXT,
                source TEXT,
                created_at REAL,
                event_ts REAL,
                ring_event_id TEXT UNIQUE,
                clip_file TEXT,
                video_status TEXT,
                vision TEXT,
                assessment TEXT,
                thumbnail TEXT,
                status TEXT DEFAULT 'new',
                note TEXT,
                acted_at REAL,
                actor TEXT,
                reminders INTEGER DEFAULT 0,
                last_alert_at REAL,
                last_alert_error TEXT
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS settings(
                home_id TEXT PRIMARY KEY,
                data TEXT,
                updated_at REAL
            )""")
    def _row(self, r: sqlite3.Row) -> dict:
        d = dict(r)
        if isinstance(d.get("vision"), str):
            try:
                d["vision"] = json.loads(d["vision"])
            except Exception:
                d["vision"] = {}
        if isinstance(d.get("assessment"), str):
            try:
                d["assessment"] = json.loads(d["assessment"])
            except Exception:
                d["assessment"] = {}
        return d
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
        with self._c() as c:
            cur = c.execute(
                """INSERT OR IGNORE INTO events(
                    id, event_id, home_id, device_id, device_name, source,
                    created_at, event_ts, ring_event_id, clip_file, video_status,
                    vision, assessment, thumbnail, status, reminders
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', 0)""",
                (
                    public_id,
                    pk,
                    home_id,
                    device_id,
                    device_name,
                    source,
                    now,
                    ts,
                    ring_event_id,
                    clip_file,
                    video_status,
                    json.dumps(vision_clean),
                    json.dumps(assessment),
                    thumbnail,
                ),
            )
            return public_id if cur.rowcount > 0 else None
    def get(self, eid: str) -> Optional[dict]:
        clean_id = str(eid).strip()
        with self._c() as c:
            # Check by id (public id 'evt_<hash>' or integer str), event_id (pk), or ring_event_id
            r = c.execute(
                """SELECT * FROM events 
                   WHERE id = ? OR event_id = ? OR id = ? OR ring_event_id = ?""",
                (clean_id, clean_id, clean_id.replace("evt_", ""), clean_id),
            ).fetchone()
            return self._row(r) if r else None
    def list_events(self, limit: int = 100, home_id: str = "default") -> List[dict]:
        with self._c() as c:
            rows = c.execute(
                """SELECT * FROM events 
                   WHERE home_id = ? 
                   ORDER BY event_ts DESC, created_at DESC LIMIT ?""",
                (home_id, limit),
            ).fetchall()
            return [self._row(r) for r in rows]
    def has_ring_event(self, ring_event_id: str) -> bool:
        if not ring_event_id:
            return False
        with self._c() as c:
            r = c.execute(
                "SELECT 1 FROM events WHERE ring_event_id = ? OR event_id = ?",
                (ring_event_id, f"ring#{ring_event_id}"),
            ).fetchone()
            return r is not None
    def set_status(
        self,
        eid: str,
        status: str,
        note: Optional[str] = None,
        actor: str = "Primary Caregiver",
    ) -> bool:
        clean_id = str(eid).strip()
        with self._c() as c:
            cur = c.execute(
                """UPDATE events 
                   SET status = ?, note = ?, acted_at = ?, actor = ? 
                   WHERE id = ? OR event_id = ? OR id = ?""",
                (status, note, time.time(), actor, clean_id, clean_id, clean_id.replace("evt_", "")),
            )
            return cur.rowcount > 0
    def unacknowledged(self, limit: int = 50, home_id: str = "default") -> List[dict]:
        with self._c() as c:
            rows = c.execute(
                """SELECT * FROM events 
                   WHERE home_id = ? AND status = 'new' 
                   ORDER BY event_ts ASC LIMIT ?""",
                (home_id, limit),
            ).fetchall()
            return [self._row(r) for r in rows]
    def mark_alerted(
        self,
        eid: str,
        expected_reminders: int,
        error: Optional[str] = None,
    ) -> bool:
        clean_id = str(eid).strip()
        now = time.time()
        with self._c() as c:
            cur = c.execute(
                """UPDATE events 
                   SET reminders = reminders + 1, last_alert_at = ?, last_alert_error = ? 
                   WHERE (id = ? OR event_id = ?) 
                     AND status = 'new' 
                     AND reminders = ?""",
                (now, error, clean_id, clean_id, expected_reminders),
            )
            return cur.rowcount > 0
    def clear(self) -> None:
        with self._c() as c:
            c.execute("DELETE FROM events")
    def get_settings(self, home_id: str = "default") -> dict:
        with self._c() as c:
            r = c.execute("SELECT data FROM settings WHERE home_id = ?", (home_id,)).fetchone()
            if r and r["data"]:
                try:
                    return json.loads(r["data"])
                except Exception:
                    pass
            return dict(DEFAULT_SETTINGS)
    def put_settings(self, settings: dict, home_id: str = "default") -> dict:
        with self._c() as c:
            c.execute(
                """INSERT INTO settings(home_id, data, updated_at) 
                   VALUES(?, ?, ?) 
                   ON CONFLICT(home_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at""",
                (home_id, json.dumps(settings), time.time()),
            )
        return settings
