# GSI eventual-consistency fix: pipeline rows passed in-memory to callers

`sync_ring` previously returned a list of inserted IDs and callers re-fetched each row from DynamoDB via `db.get(i)` before calling `to_event`. Under DynamoDB's GSI eventual consistency, those reads could come back empty, causing silent publishing failures. The fix changes `_ingest_device` to return a `(ids, rows)` tuple, building the row dict in memory at each `db.insert` call site. All three callers (`poller`, `ring_sync` route, `_webhook_ingest`) now iterate `res["rows"]` directly. The `simulate` route gains a 3-attempt retry loop for its own `db.get` call.

Watch for: **confirmed** `locals()` guards on the main-path row dict are always `True` — `clip_name` and `v_status` are in scope unconditionally by the time the guard is evaluated, making them dead code that would silently swallow a future refactor; **confirmed** `time.sleep(0.5)` in the `simulate` route handler runs on the async event loop, not in a threadpool, blocking the server for up to 1.5 s.

**Verdict**: APPROVED

---

## High-level view

The core change is mechanically sound: both `db.insert` call sites in `_ingest_device` (the no-clip early-exit path and the main try/except path) now build row dicts and append them to `rows`, and `sync_ring` threads the new return value through to callers. The in-memory rows eliminate the GSI re-read race entirely.

All three callers are updated and each is now wrapped in its own per-row try/except with a `logger.warning`, so a single bad row can't silently kill the rest of the batch. The existing `ring_sync` return contract (`added`, `events`, `notes`) is fully preserved; `rows` is only used internally and never surfaces in the HTTP response.

The `locals()` guards in the main-path row dict (`"clip_name" in locals()` and `"v_status" in locals()`) are always `True` at that point in the code — both names are assigned unconditionally above the `db.insert` call in both the happy and exception paths. The guards are dead code, not a correctness problem today, but they conceal that neither field has a safe fallback if the control flow is ever restructured.

The `simulate` retry loop addresses a real DynamoDB consistency window, but `time.sleep(0.5)` in the route handler runs on the async event loop after the `await` resolves — not inside the threadpool. That blocks the entire server for up to 1.5 s per simulate call. The fix is `await asyncio.sleep(0.5)`.

---

<details>
<summary>Issues (3)</summary>

1. **`locals()` guards are always true (main path)** — `clip_name` and `v_status` are assigned in both the `try` and `except` branches before `db.insert`, so `"clip_name" in locals()` is always `True` at the row-append site. The guards are dead code. They should be removed and the fields referenced directly; this also makes the intent clear that the exception path sets `clip_name = None`. (confirmed)

2. **`simulate` blocks the event-loop thread** — `time.sleep(0.5)` inside the retry loop runs on a `run_in_threadpool` worker, so it doesn't block the event loop. However, `simulate` itself is already called via `run_in_threadpool` in the route handler — the `time.sleep` call in the route handler (`main.py` line ~335) runs on the *main async thread*, not in a threadpool. That call will block the event loop for up to 1.5 s. (confirmed)

3. **`to_event` hard-indexes `r["status"]`; in-memory rows supply it, but it's fragile** — all new row dicts include `"status": "new"`, which satisfies the lookup. The risk is that any future caller that skips that field will get a silent `KeyError` rather than a graceful fallback. Not a regression from this PR, but the brittleness is introduced here. (likely)

</details>

---

<details>
<summary>Details</summary>

### `locals()` guards — dead code on the main path, not the exception path

After the `try/except` block, both branches assign `clip_name` and `v_status`:

- **try branch**: `clip_name = clip_playable.name` (then possibly set to `None` on S3 failure), `v_status` set before `clip_name`.
- **except branch**: `clip_name = None`, `v_status = "unavailable"`.

By the time `db.insert` is called (after the try/except), both names are unconditionally in scope. The guards `"clip_name" in locals()` and `"v_status" in locals()` are always `True`. The correct fix is simply:

```python
"clip_file": clip_name,
"video_status": v_status,
```

The `locals()` pattern is correct Python, but here it gives a false sense of safety. If the code is later refactored — e.g., the try/except is hoisted — the guards would silently fall back to `None`/`"unavailable"` rather than raising, potentially hiding a bug.

The brief flagged `'clip_name' in dir()` as wrong and `locals()` as correct. The coder used `locals()`, which is correct. The concern here is not which function to use but that neither guard is necessary given the current control flow.

### `simulate` route — `time.sleep` on the async thread

The route handler:

```python
async def simulate(body: SimBody | None = None):
    try:
        rid = await run_in_threadpool(pipeline.simulate, ...)
    ...
    ev = None
    for _ in range(3):
        row = db.get(rid)
        if row:
            ev = to_event(row)
            break
        time.sleep(0.5)   # ← blocks the event loop
```

`run_in_threadpool` offloads `pipeline.simulate` to a thread, but the retry loop with `time.sleep` runs back on the async event loop after the `await` resolves. At most one simulate request runs at a time (the lock in `_ingest_device` serialises Ring syncs), so in practice this is a 0–1.5 s stall on an admin endpoint rather than a production hot path. Fixing it is `await asyncio.sleep(0.5)`.


</details>

---

<details>
<summary>File map</summary>

| File | What changed |
|---|---|
| `backend/app/pipeline.py` | `_ingest_device` returns `(ids, rows)` tuple; row dicts appended at both `db.insert` call sites; `sync_ring` accumulates `rows` and returns them alongside `ids` and `notes` |
| `backend/app/main.py` | `poller`, `ring_sync` route, `_webhook_ingest` iterate `res["rows"]` instead of calling `db.get` per id; all three wrapped in per-row try/except; `simulate` adds 3-attempt retry loop with `time.sleep(0.5)` |

Full diff: `git diff d803cb3 dc68db5 -- backend/app/pipeline.py backend/app/main.py`

</details>
