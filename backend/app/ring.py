"""Minimal Ring Partner API client (server-side only: tokens never reach the browser)."""
import json, os, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("RING_API_BASE", "https://api.amazonvision.com")
OAUTH_URL = "https://oauth.ring.com/oauth/token"
TOKEN_FILE = Path(".ring_tokens.json")


class RingError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"Ring API {status}: {message}")
        self.status, self.message = status, message


class RingAuthError(RingError):
    pass


class MediaNotReady(RingError):
    """No recording for that window (yet), or window not authorised."""


def _find(obj, key):
    """Recursively find the first value for `key` in nested dict/list."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find(v, key)
            if r is not None:
                return r
    return None


def to_ms(v):
    """Accept epoch s/ms (int or numeric str) or ISO-8601 -> epoch ms."""
    if v is None:
        return None
    try:
        n = float(v)
        return int(n * 1000) if n < 1e11 else int(n)
    except (TypeError, ValueError):
        pass
    try:
        return int(datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


class RingClient:
    def __init__(self):
        self.access_token = os.getenv("RING_ACCESS_TOKEN", "").strip() or None
        self.refresh_token = os.getenv("RING_REFRESH_TOKEN", "").strip() or None
        self.client_id = os.getenv("RING_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("RING_CLIENT_SECRET", "").strip()
        self.expires_at = 0.0
        self.http = requests.Session()
        if TOKEN_FILE.exists():  # rotated refresh token from a previous run
            try:
                saved = json.loads(TOKEN_FILE.read_text())
                self.refresh_token = saved.get("refresh_token") or self.refresh_token
            except Exception:
                pass

    # ---- auth -------------------------------------------------------
    @property
    def can_refresh(self):
        return bool(self.refresh_token and self.client_id and self.client_secret)

    @property
    def configured(self):
        return bool(self.access_token or self.can_refresh)

    def set_access_token(self, token: str):
        self.access_token = token.strip()
        self.expires_at = 0.0

    def _refresh(self):
        r = self.http.post(OAUTH_URL, timeout=30, data={
            "grant_type": "refresh_token", "refresh_token": self.refresh_token,
            "client_id": self.client_id, "client_secret": self.client_secret})
        if r.status_code != 200:
            raise RingAuthError(r.status_code, f"token refresh failed: {r.text[:200]}")
        j = r.json()
        self.access_token = j["access_token"]
        self.refresh_token = j.get("refresh_token", self.refresh_token)  # rotates every refresh
        self.expires_at = time.time() + int(j.get("expires_in", 14400)) - 120
        TOKEN_FILE.write_text(json.dumps({"refresh_token": self.refresh_token}))

    def _token(self):
        if self.can_refresh and (not self.access_token or (self.expires_at and time.time() > self.expires_at)):
            self._refresh()
        if not self.access_token:
            raise RingAuthError(401, "No Ring token configured")
        return self.access_token

    # ---- http -------------------------------------------------------
    def _request(self, method, path, _retry=True, **kw):
        url = path if path.startswith("http") else API_BASE + path
        hdrs = {"Authorization": f"Bearer {self._token()}"}
        r = self.http.request(method, url, headers=hdrs, allow_redirects=False, timeout=90, **kw)
        api_host = urlparse(API_BASE).netloc
        for _ in range(3):  # redirects
            if r.status_code not in (301, 302, 303, 307, 308):
                break
            loc = urljoin(url, r.headers["Location"])
            host = urlparse(loc).netloc
            if host == api_host or host.endswith("amazonvision.com"):
                # Ring-internal hop: keep the token; 303 means "now GET", others repeat the request
                m, extra = ("GET", {}) if r.status_code == 303 else (method, kw)
                r = self.http.request(m, loc, headers=hdrs, allow_redirects=False, timeout=90, **extra)
            else:
                r = self.http.get(loc, timeout=120)  # pre-signed storage URL: never send the Ring token
                break
        if r.status_code == 401 and _retry and self.can_refresh:
            self._refresh()
            return self._request(method, path, _retry=False, **kw)
        if r.status_code in (401,):
            raise RingAuthError(401, "Token expired/invalid. Playground tokens last ~30 min - paste a fresh one.")
        return r

    # ---- API --------------------------------------------------------
    def devices(self):
        r = self._request("GET", "/v1/devices")
        if r.status_code != 200:
            raise RingError(r.status_code, r.text[:300])
        out = []
        for d in r.json().get("data", []):
            a = d.get("attributes", {}) or {}
            name = next((a[k] for k in ("name", "device_name", "display_name", "label") if a.get(k)), None)
            out.append({"id": d["id"], "name": name or f"Ring device {str(d['id'])[-6:]}", "attributes": a})
        return out

    def device_online(self, device_id):
        r = self._request("GET", f"/v1/devices/{device_id}/status")
        if r.status_code != 200:
            return None
        v = _find(r.json(), "online")
        return bool(v) if v is not None else None

    def events(self, device_id, event_types="motion,on_demand,ding", limit=25):
        """Newest-first event history (first page only)."""
        r = self._request("GET", f"/v1/history/devices/{device_id}/events", params={"event_types": event_types})
        if r.status_code != 200:
            raise RingError(r.status_code, r.text[:300])
        out = []
        for e in r.json().get("data", [])[:limit]:
            a = e.get("attributes", {}) or {}
            start = None
            for k in ("start_time", "started_at", "start_ms", "timestamp", "time", "start", "created_at"):
                start = to_ms(a.get(k))
                if start:
                    break
            out.append({"id": str(e.get("id")), "event_type": a.get("event_type", "motion"),
                        "sub_type": a.get("sub_type"), "start_ms": start, "raw": a})
        return out

    def clip(self, device_id, start_ms, duration_ms=10000, retry_seconds=0):
        """Download an MP4. Retries while Ring is still processing the recording."""
        deadline, wait = time.time() + retry_seconds, 2.0
        body = {"timestamp": int(start_ms), "duration": int(duration_ms)}
        while True:
            r = self._request("POST", f"/v1/devices/{device_id}/media/video/download", json=body)
            if r.status_code in (200, 206):
                return r.content
            if r.status_code in (403, 416, 425):
                if time.time() < deadline:
                    time.sleep(wait); wait = min(wait * 1.5, 8); continue
                raise MediaNotReady(r.status_code, r.text[:200])
            raise RingError(r.status_code, r.text[:300])


ring = RingClient()
