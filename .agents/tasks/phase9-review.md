# Phase 9: S3 clip hosting and container deployment

This phase adds S3-backed clip storage and a production hosting layer: a Docker image built from `python:3.12-slim`, ECR/App Runner deploy scripts, and an Amplify config for the frontend. Clips can now be uploaded to S3 on ingest and served via short-lived pre-signed URLs rather than from disk. The `CLIPS_BACKEND=local` path is structurally unchanged.

Watch for: `apprunner.yaml` specifies Python 3.11 and its runtime hardcodes port 8080 while the Dockerfile targets Python 3.12 and port 8000 — **these are two incompatible runtime descriptors and neither fully aligns with the other (confirmed)**. Also, the S3 upload in `simulate()` ignores the boolean return value of `_upload_clip_to_s3`, so `clip_file` can name a key that no longer exists locally and has not been confirmed uploaded (confirmed).

**Verdict**: NEEDS_CHANGES

---

## High-level view

The Dockerfile meets all structural requirements: correct base image, OpenCV system deps, no secrets baked in, `VOLUME` for local clip persistence, and the expected `CMD`. The `pip install` runs against the correct path via `-r backend/requirements.txt` before `WORKDIR` is switched to `/app/backend`.

`_upload_clip_to_s3` is a non-raising helper that wraps boto3 in a broad `try/except`, logs a warning on failure, deletes the local file only after a confirmed upload, and returns a bool. Both `simulate()` and `_ingest_device()` gate the S3 call behind `CLIPS_BACKEND == "s3" and S3_BUCKET`, keeping the local path untouched.

There's a subtle gap in `simulate()`: it calls `_upload_clip_to_s3(clip_playable)` but ignores the return value, then unconditionally stores `clip_playable.name` as `clip_file` in the database. If the upload silently fails, the DB record points to a key that exists neither in S3 nor locally (the local delete also won't have happened, so the disk copy survives — but the clip route will still try to generate a pre-signed URL for a nonexistent key and succeed in generating one that returns a 403/404 from S3). `_ingest_device()` has the same pattern.

The `clip()` route in `main.py` correctly generates a pre-signed URL with `ExpiresIn=900`, returns a `302 RedirectResponse`, imports `RedirectResponse`, and falls through to local `FileResponse` on any exception. The health endpoint exposes `clips_backend` and `s3_bucket` (as a bool, not the bucket name — appropriate).

`apprunner.yaml` is problematic on two counts. First, it declares `runtime: python311` and `runtime-version: "3.11"` while the Dockerfile and the project's stated stack are Python 3.12. If App Runner consumes this file directly, it will provision a 3.11 managed runtime instead of running the Docker image. Second, the `run.command` uses port 8080, not 8000. The Dockerfile exposes 8000, `deploy-backend.sh` documents 8000 in its next-steps output, and the review criteria specify 8000. A container deployed from the ECR image will bind to 8000 and App Runner's managed runtime will expect 8080 — the service will not receive traffic.

`amplify.yml`, both deploy scripts, `.env.example`, and `.gitignore` all conform to the spec: no hardcoded values, env vars fail-fast via `:` parameter expansion, CloudFront invalidation is conditional, and the new `.gitignore` entry for `infra/*.env` closes the one gap where a per-environment deploy config could have been accidentally committed.

---

<details>
<summary>Issues (3)</summary>

1. **apprunner.yaml Python version mismatch** — `runtime: python311` and `runtime-version: "3.11"` conflict with the project's Python 3.12 stack (Dockerfile uses `python:3.12-slim`). Change both to `python312` / `"3.12"`, or remove the file if App Runner is expected to run the Docker image rather than a managed runtime.

2. **apprunner.yaml port mismatch** — `run.command` binds to port 8080, but the Docker image exposes 8000 and `deploy-backend.sh` documents 8000. App Runner will route traffic to 8080 but the container listens on 8000 — the service will not respond. Change the port in `apprunner.yaml` to 8000 (or align the Dockerfile and deploy script to 8080 if that was intentional).

3. **Ignored upload return value in simulate() and _ingest_device()** — Both callers discard the `bool` returned by `_upload_clip_to_s3`, then unconditionally record `clip_file` as if upload succeeded. On failure the local file is not deleted (correct) but `clip_file` is stored in the DB pointing to a key that S3 doesn't have. The clip route will generate a valid-looking pre-signed URL that resolves to a 403/404 from S3. Fix: check the return value and set `clip_file = None` (or a sentinel) when the upload fails.

</details>

---

<details>
<summary>Details</summary>

### apprunner.yaml runtime / port conflict

The file specifies `runtime: python311` and `runtime-version: "3.11"` at the top, then `run.command: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080`. The Dockerfile targets `python:3.12-slim` and `EXPOSE 8000`; the CMD in the Dockerfile uses `--port 8000`. `deploy-backend.sh` prints `--port 8000` in its next-steps guidance.

If App Runner is intended to run the Docker image from ECR, the `apprunner.yaml` file is acting as configuration for the _managed runtime_ path — a separate code-based deployment mode that doesn't use a container image. Using it alongside a Docker-based deployment sends contradictory signals to the operator and will cause confusion. If it exists to document App Runner settings, it should either be removed or converted to a comment block. If App Runner's image-based deployment reads a `apprunner.yaml` to determine port routing, then port 8080 vs 8000 is a live misconfiguration.

Either way, both the Python version and the port need to align with the Dockerfile before this file can be trusted.

### Ignored upload result in simulate()

```python
if CLIPS_BACKEND == "s3" and S3_BUCKET:
    _upload_clip_to_s3(clip_playable)   # return value discarded
video_status = "sample"
```

`clip_file` is set to `clip_playable.name` before this block and is never cleared on failure. When `_upload_clip_to_s3` returns `False` (network error, bad credentials, bucket not found), the local file still exists on disk, but the DB record stores the clip name as if it's in S3. The `clip()` route will call `generate_presigned_url` for `clips/<filename>`, succeed (the presigned URL is generated regardless of whether the object exists), and return a 302 to a URL that S3 will reject with `NoSuchKey`. The same pattern is in `_ingest_device()`.

Fix in both callers: check the return value and set `video_status = "s3_upload_failed"` (retaining `clip_file` for local fallback while the file is still on disk) rather than recording a name that implies successful S3 storage. In a containerized environment with an ephemeral filesystem, the fallback is only meaningful within the same container lifetime — the right long-term fix is to surface the upload failure in `video_status` and return a 503 from the clip route rather than a broken pre-signed URL.

### .dockerignore and secret hygiene

`.dockerignore` excludes `backend/.env`, `backend/*.db`, and clip files. `.gitignore` adds `infra/*.env`. Neither the Dockerfile nor either deploy script hardcodes any credential, bucket name, region, or token.

</details>

---

<details>
<summary>File map</summary>

| File | What changed |
|---|---|
| `Dockerfile` | New file — Python 3.12-slim image with OpenCV deps, copies backend, VOLUME, EXPOSE 8000 |
| `.dockerignore` | New file — excludes .env, .db, clips, node_modules, dist, .git, frontend source |
| `backend/app/pipeline.py` | Added `_upload_clip_to_s3` helper; `simulate()` and `_ingest_device()` call it when `CLIPS_BACKEND=s3` |
| `backend/app/main.py` | `clip()` route: S3 pre-signed URL with 302 redirect, local FileResponse fallback; `health()` adds `clips_backend` and `s3_bucket` |
| `backend/.env.example` | S3 block appended: `CLIPS_BACKEND`, `S3_BUCKET`, `S3_REGION` |
| `infra/apprunner.yaml` | New file — App Runner managed-runtime config (Python 3.11, port 8080 — conflicts with Dockerfile) |
| `infra/deploy-backend.sh` | New file — Docker build → ECR push, env-var-driven, no hardcoded values |
| `infra/deploy-frontend.sh` | New file — npm build → S3 sync with --delete, optional CloudFront invalidation |
| `amplify.yml` | New file — Amplify frontend pipeline: npm install → npm run build → dist |
| `.gitignore` | Added `infra/*.env` exclusion |

Full diff: `git diff main` from the repo root.

</details>
