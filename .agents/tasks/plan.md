# Implementation Plan — Fix new Ring events not appearing in the dashboard

## Root Cause Summary

`poller`, `ring_sync`, and `_webhook_ingest` all call `db.get(i)` after `pipeline.sync_ring()` returns
a list of public event ids (`evt_<hash>`). On DynamoDB, `db.get()` goes through `_resolve_pk()`, which
queries the `by-public-id` GSI. Because DynamoDB GSIs have eventual consistency, a freshly-written item
may not be visible in that GSI for 1-2 seconds after `put_item`. `db.get(i)` returns `None`,
`to_event(None)` raises a `KeyError`, the exception is swallowed by the caller's `except Exception`,
and nothing is published to the SSE stream. The frontend never sees the new event.

The fix avoids the GSI entirely by building the row dict in memory inside `_ingest_device`, alongside
each successful `db.insert()` call, then propagating it up through `sync_ring` → `poller`/`ring_sync`/
`_webhook_ingest`. For the `simulate` route (which has a short code path) a 3-attempt retry loop
around `db.get(rid)` is sufficient.

---

## Part 1 — `backend/app/pipeline.py`: Return rows alongside IDs

### Item 1 — Add `rows` list and row-building in the fallback `db.insert` path inside `_ingest_device`

**Function anchor:** `_ingest_device` → the `if path is None` branch that calls `db.insert` and
`continue`s. This is the fallback when Ring clip download fails and no sample fallback clip exists.

**What to do:**
Change the signature to collect `rows` alongside `ids`. In the early-exit `db.insert` (fallback path),
build a row dict immediately after the insert and append it to `rows`. Only append when `rid` is not None
(same guard as the existing `if rid: ids.append(rid)` check).

**Files:** `backend/app/pipeline.py`

**Exact location:**  
Function `_ingest_device` starts at line 109 (`def _ingest_device(...)`).  
The fallback `db.insert` call is inside the `if path is None:` block, around lines 152-158.

**Before (the fallback path only, simplified):**
```python
def _ingest_device(dev: dict, limit: int, wait: int, notes: list) -> list:
    ...
    ids = []
    for e in reversed(fresh):
        ...
        if path is None:
            samples = sample_clips() if allow_fallback else []
            if samples:
                path, source = random.choice(samples), "ring+sample-clip"
            else:
                vision = {"error": "Ring clip unavailable and sample fallback disabled"}
                rid = db.insert(dev["id"], dev["name"], "ring", vision, assess(meta, vision), None,
                                event_ts=start / 1000, ring_event_id=e["id"], video_status="unavailable")
                if rid:
                    ids.append(rid)
                continue
        ...
    return ids
```

**After:**
```python
def _ingest_device(dev: dict, limit: int, wait: int, notes: list) -> tuple[list, list]:
    ...
    ids, rows = [], []
    for e in reversed(fresh):
        ...
        if path is None:
            samples = sample_clips() if allow_fallback else []
            if samples:
                path, source = random.choice(samples), "ring+sample-clip"
            else:
                vision = {"error": "Ring clip unavailable and sample fallback disabled"}
                result = assess(meta, vision)
                rid = db.insert(dev["id"], dev["name"], "ring", vision, result, None,
                                event_ts=start / 1000, ring_event_id=e["id"], video_status="unavailable")
                if rid:
                    ids.append(rid)
                    rows.append({
                        "id": rid, "event_id": rid,
                        "device_id": dev["id"], "device_name": dev["name"],
                        "source": "ring",
                        "event_ts": start / 1000,
                        "status": "new",
                        "vision": vision,
                        "assessment": result,
                        "thumbnail": None,
                        "clip_file": None,
                        "video_status": "unavailable",
                    })
                continue
        ...
    return ids, rows
```

**Edge case:** The original code re-used the local `assess(meta, vision)` call but discarded the result
into a throwaway. Assign it to `result` before calling `db.insert` so the row dict can reference the
same object without calling `assess` twice.

**Verify:** `cd backend && /Users/family/Documents/RingCareAI/.venv/bin/pytest tests/ -q` — all existing tests pass (no caller of `_ingest_device` outside `sync_ring`, so no breakage yet; `sync_ring` is updated in the next item).

---

### Item 2 — Add row-building in the main `db.insert` path inside `_ingest_device`

**What to do:**
After the `try/except` block that calls `process_clip`, `make_playable`, and optionally uploads to S3,
there is a single `db.insert(...)` call that covers the happy path (real Ring clip or sample-fallback
clip). Add row construction immediately after that insert, mirroring the structure from Item 1.

**Files:** `backend/app/pipeline.py`

**Exact location:**  
Still inside `_ingest_device`. The main-path `db.insert` is the last statement of the `for e in reversed(fresh):` loop body, around lines 176-179:

```python
        rid = db.insert(dev["id"], dev["name"], source, vision, result, thumb, event_ts=start / 1000,
                        ring_event_id=e["id"], clip_file=clip_name, video_status=v_status)
        if rid:
            ids.append(rid)
```

**Before:**
```python
        rid = db.insert(dev["id"], dev["name"], source, vision, result, thumb, event_ts=start / 1000,
                        ring_event_id=e["id"], clip_file=clip_name, video_status=v_status)
        if rid:
            ids.append(rid)
```

**After:**
```python
        rid = db.insert(dev["id"], dev["name"], source, vision, result, thumb, event_ts=start / 1000,
                        ring_event_id=e["id"], clip_file=clip_name, video_status=v_status)
        if rid:
            ids.append(rid)
            rows.append({
                "id": rid, "event_id": rid,
                "device_id": dev["id"], "device_name": dev["name"],
                "source": source,
                "event_ts": start / 1000,
                "status": "new",
                "vision": vision,
                "assessment": result,
                "thumbnail": thumb,
                "clip_file": clip_name,
                "video_status": v_status,
            })
```

**Edge case — `vision`/`result`/`thumb`/`clip_name`/`v_status` from the `except` branch:**  
When `process_clip` raises, the `except Exception` block reassigns `vision`, `result`, `thumb`,
`clip_name`, and `v_status` before reaching the `db.insert` call. The row dict is built _after_ the
insert, so it naturally picks up whichever values are in scope — no special handling needed.

**Edge case — `source` for sample-fallback clips:**  
When `path` was `None` but samples existed, `source` was already overwritten to `"ring+sample-clip"`.
The row dict captures this correctly because it uses the local `source` variable.

**Verify:** `cd backend && /Users/family/Documents/RingCareAI/.venv/bin/pytest tests/ -q` — all existing tests pass.

---

### Item 3 — Change `_ingest_device` return value and update `sync_ring`

**What to do:**
The function now returns `(ids, rows)`. Update the `return ids` at the end of `_ingest_device` to
`return ids, rows`. Then update `sync_ring` to unpack the tuple, aggregate both lists, and include
`"rows"` in its return dict.

**Files:** `backend/app/pipeline.py`

**Before (`_ingest_device` tail):**
```python
    return ids
```

**After:**
```python
    return ids, rows
```

**Before (`sync_ring`):**
```python
def sync_ring(limit=5, wait=0, only_device: str | None = None) -> dict:
    """Pull new events + clips from Ring. Returns {'ids': [...], 'notes': [...]}."""
    if not ring.configured:
        raise RingError(400, "Ring is not configured. Set RING_ACCESS_TOKEN (Playground) in backend/.env")
    notes, ids = [], []
    with _lock:
        devices = ring.devices()
        if only_device:
            devices = [d for d in devices if d["id"] == only_device] or [{"id": only_device, "name": "Ring device"}]
        for d in devices:
            ids += _ingest_device(d, limit, wait, notes)
    return {"ids": ids, "notes": notes}
```

**After:**
```python
def sync_ring(limit=5, wait=0, only_device: str | None = None) -> dict:
    """Pull new events + clips from Ring. Returns {'ids': [...], 'rows': [...], 'notes': [...]}."""
    if not ring.configured:
        raise RingError(400, "Ring is not configured. Set RING_ACCESS_TOKEN (Playground) in backend/.env")
    notes, ids, rows = [], [], []
    with _lock:
        devices = ring.devices()
        if only_device:
            devices = [d for d in devices if d["id"] == only_device] or [{"id": only_device, "name": "Ring device"}]
        for d in devices:
            new_ids, new_rows = _ingest_device(d, limit, wait, notes)
            ids += new_ids
            rows += new_rows
    return {"ids": ids, "rows": rows, "notes": notes}
```

**Edge case — backward compatibility:**  
`res["ids"]` continues to exist in the return dict, so any code that still reads `res["ids"]` (e.g.
tests) will not break. The new `res["rows"]` key is additive.

**Verify:** `cd backend && /Users/family/Documents/RingCareAI/.venv/bin/pytest tests/ -q` — all existing tests pass.

---

## Part 2 — `backend/app/main.py`: Use rows directly

### Item 4 — Fix `poller` to iterate `res["rows"]` instead of calling `db.get(i)`

**Function anchor:** `async def poller(seconds: int)` in `main.py`.

**Exact location:** The `for i in res["ids"]:` loop is inside the `try` block, after
`res = await run_in_threadpool(pipeline.sync_ring)`, around lines 95-97.

**Before:**
```python
            for i in res["ids"]:
                publish(to_event(db.get(i)))
```

**After:**
```python
            for row in res.get("rows") or []:
                try:
                    publish(to_event(row))
                except Exception as row_exc:
                    logger.warning(f"[poll] Failed to publish event {row.get('id')}: {row_exc}")
```

**Rationale for `res.get("rows") or []`:**  
Defensive: if `sync_ring` somehow returns a dict without `"rows"` (e.g. an older cached import during a
hot-reload), the poller degrades gracefully to a no-op instead of crashing.

**Edge case — `to_event(row)` KeyError risk:**  
`to_event` accesses `r["vision"]` and `r["assessment"]` directly (no `.get()`). Both are always set by
the row-building code above (the fallback path and main path both set them). No risk.

**Verify:** `cd backend && /Users/family/Documents/RingCareAI/.venv/bin/pytest tests/test_polling_webhook.py -q` — all tests pass.

---

### Item 5 — Fix `ring_sync` route to iterate `res["rows"]` instead of calling `db.get(i)`

**Function anchor:** `async def ring_sync(body: SyncBody | None = None)` in `main.py`.

**Exact location:** The list comprehension `[to_event(db.get(i)) for i in res["ids"]]` is around
lines 222-224.

**Before:**
```python
    events = [to_event(db.get(i)) for i in res["ids"]]
    for e in events:
        publish(e)
    return {"added": len(events), "events": [{**e, "thumbnail": None} for e in events], "notes": res["notes"]}
```

**After:**
```python
    events = []
    for row in res.get("rows") or []:
        try:
            ev = to_event(row)
            events.append(ev)
            publish(ev)
        except Exception as row_exc:
            logger.warning(f"[ring_sync] Failed to convert event {row.get('id')}: {row_exc}")
    return {"added": len(events), "events": [{**e, "thumbnail": None} for e in events], "notes": res["notes"]}
```

**Edge case — `res["notes"]` always present:**  
`sync_ring` always returns `"notes"` so `res["notes"]` is safe without `.get()`.

**Verify:** `cd backend && /Users/family/Documents/RingCareAI/.venv/bin/pytest tests/test_polling_webhook.py tests/test_event_reliability.py -q` — all tests pass.

---

### Item 6 — Fix `_webhook_ingest` to iterate `res["rows"]` instead of calling `db.get(i)`

**Function anchor:** `async def _webhook_ingest(device_id, ring_event_id)` in `main.py`.

**Exact location:** The `for i in res["ids"]:` loop, around lines 232-233.

**Before:**
```python
        res = await run_in_threadpool(pipeline.sync_ring, 3, 40, device_id)  # wait up to 40s for the clip
        for i in res["ids"]:
            publish(to_event(db.get(i)))
```

**After:**
```python
        res = await run_in_threadpool(pipeline.sync_ring, 3, 40, device_id)  # wait up to 40s for the clip
        for row in res.get("rows") or []:
            try:
                publish(to_event(row))
            except Exception as row_exc:
                logger.warning(f"[webhook] Failed to publish event {row.get('id')}: {row_exc}")
```

**Edge case — webhook wraps everything in `except Exception`:**  
The outer `try/except Exception` in `_webhook_ingest` already catches pipeline-level failures.
The per-row `try/except` inside the loop is an _inner_ guard so one bad row never silences
the remaining rows. The outer guard still handles `run_in_threadpool` failures.

**Verify:** `cd backend && /Users/family/Documents/RingCareAI/.venv/bin/pytest tests/test_polling_webhook.py -q` — all tests pass.

---

## Part 3 — `backend/app/main.py`: Simulate route retry loop

### Item 7 — Add GSI retry loop in the simulate route

**Function anchor:** `async def simulate(body: SimBody | None = None)` in `main.py`.

**Exact location:** The single call `ev = to_event(db.get(rid))` immediately after
`rid = await run_in_threadpool(pipeline.simulate, ...)`, around lines 270-271.

**Before:**
```python
@app.post("/api/events/simulate")
async def simulate(body: SimBody | None = None):
    try:
        rid = await run_in_threadpool(pipeline.simulate, body.video if body else None)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    ev = to_event(db.get(rid))
    publish(ev)
    return ev
```

**After:**
```python
@app.post("/api/events/simulate")
async def simulate(body: SimBody | None = None):
    try:
        rid = await run_in_threadpool(pipeline.simulate, body.video if body else None)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    # Retry up to 3 times (0.5 s apart) to allow DynamoDB GSI eventual consistency
    ev_row = None
    for _attempt in range(3):
        ev_row = db.get(rid)
        if ev_row is not None:
            break
        await asyncio.sleep(0.5)
    if ev_row is None:
        raise HTTPException(500, "Event stored but could not be retrieved")
    ev = to_event(ev_row)
    publish(ev)
    return ev
```

**Edge case — SQLite backend:**  
SQLite's `get()` queries by column directly (no GSI), so it always returns the row immediately after
insert. The retry loop exits on the first iteration with zero extra delay. No behavioral change for
SQLite users.

**Edge case — `pipeline.simulate` returns `None`:**  
`db.insert` returns `None` when the item already exists (idempotent insert). `pipeline.simulate` passes
the return value of `db.insert` straight through. If `rid` is `None`, `db.get(None)` will be called.
Both SQLite and DynamoDB `get()` handle a `None`/empty input gracefully (return `None`). The retry loop
will exhaust all 3 attempts and raise the `HTTPException(500)`. This is acceptable — a duplicate
simulate is a logic error, not a GSI race, and the 500 surfaces it honestly. If silent deduplication
is preferred in the future, guard with `if rid is None: raise HTTPException(409, "Duplicate event")`.

**Verify:** `cd backend && /Users/family/Documents/RingCareAI/.venv/bin/pytest tests/ -q` — all existing tests pass. Then manually:
```
curl -s -X POST "http://localhost:8000/api/events/simulate" \
  -H "Content-Type: application/json" \
  -d '{"video": "sample_walk.mp4"}' | python3 -m json.tool | grep -E '"id"|"severity"|"aiStatus"'
```
Expect an event dict with `"id"`, `"severity"`, and `"aiStatus"` fields (not a 500).

---

## New tests to add (Item 8)

**What to do:** Add a new test file `backend/tests/test_gsi_fix.py` covering:

1. `_ingest_device` returns a tuple `(ids, rows)` and each row dict has the required keys.
2. `sync_ring` result dict has `"ids"`, `"rows"`, and `"notes"` keys.
3. `poller` publishes events from `res["rows"]` without calling `db.get`.
4. `ring_sync` route builds its response from `res["rows"]` without calling `db.get`.
5. `_webhook_ingest` calls `publish` from `res["rows"]` without calling `db.get`.
6. Simulate route returns 200 even when `db.get` returns `None` on the first attempt (mock to
   return `None` once, then the real row on the second attempt).
7. Simulate route returns HTTP 500 when `db.get` returns `None` on all 3 attempts.

**Files:** `backend/tests/test_gsi_fix.py` (new file)

**Verify:** `cd backend && /Users/family/Documents/RingCareAI/.venv/bin/pytest tests/test_gsi_fix.py -v` — all new tests pass. Then run the full suite:
`cd backend && /Users/family/Documents/RingCareAI/.venv/bin/pytest tests/ -q` — all tests pass.

---

## Dependency order

Items must be applied in order: 1 → 2 → 3 (pipeline changes) → 4 → 5 → 6 → 7 (main.py changes) → 8 (tests).  
Items 4, 5, 6, and 7 each depend on Item 3 (`sync_ring` returning `"rows"`).  
Items 4, 5, and 6 are independent of each other and of Item 7.  
Item 8 depends on all prior items being complete.

## Run command

```bash
cd /Users/family/Documents/RingCareAI/backend
/Users/family/Documents/RingCareAI/.venv/bin/pytest tests/ -q
```
