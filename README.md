# RingCare AI

Ring event -> FastAPI -> OpenCV -> AI assessment -> React dashboard.

## Run (two terminals)

**1. Backend** (Python 3.10+)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # Windows: copy .env.example .env
# edit .env: paste RING_ACCESS_TOKEN (Playground token); optionally ANTHROPIC_API_KEY
python -m uvicorn app.main:app --reload --port 8000
```
Check http://localhost:8000/api/health and http://localhost:8000/docs

**2. Frontend**
```bash
npm install
npm run dev          # http://localhost:3000  (proxies /api -> :8000)
```

## Getting clips from Ring
1. In the Ring Developer Playground, copy the access token (valid ~30 min) into `backend/.env` as `RING_ACCESS_TOKEN`
   - or hot-swap without restarting: `curl -X POST localhost:8000/api/ring/token -H "Content-Type: application/json" -d '{"access_token":"..."}'`
2. In the Playground, simulate a live-view / motion event.
3. In the dashboard click **Fetch Ring Events**. The backend lists device events, downloads each MP4 clip
   (`POST /v1/devices/{id}/media/video/download`), runs OpenCV + the AI assessment, stores it and pushes it to the dashboard live (SSE).

Optional: `RING_POLL_SECONDS=30` to poll automatically; or expose `/api/webhooks/ring` (e.g. via ngrok) and set `RING_HMAC_KEY` for push delivery.

If Ring has no downloadable clip for an event, the backend (when `RING_SAMPLE_FALLBACK=true`) analyses a local sample clip and labels the event
"Ring clip unavailable - analysed a local SAMPLE clip". Set it to `false` to disable.

Without a Ring token the button analyses local clips in `backend/clips/` (two synthetic placeholders are generated on first start;
drop real walking/sitting/lying `.mp4` files there for a meaningful demo).

The tool reports *review priority*, never a confirmed fall or emergency.
