# RingCare AI

AI-assisted security and safety alerts for Ring cameras.
Ring event -> FastAPI backend -> OpenCV + Amazon Rekognition -> rules-based assessment -> React dashboard + alerts.

It flags events for human review. It does **not** confirm crimes, falls or emergencies, and it can miss things or raise false alarms.

## Contents
1. [Quickstart without a Ring token (for judges)](#quickstart-without-a-ring-token-for-judges)
2. [Full setup with Ring and AWS](#full-setup-with-ring-and-aws)
3. [How it works](#how-it-works) - [Limitations](#limitations) - [Credits](#test-footage-credits) - [License](#license)

---

## Quickstart without a Ring token (for judges)

No Ring account, Ring token or AWS account is needed. You will use **three terminal windows**:
one for the backend, one for the dashboard, one to run the test commands.

The test clips `fall1.mp4`, `fall2.mp4`, `fall3.mp4` and `Ring1.mp4` are already in `backend/clips/`.

### Step 0. Install the prerequisites
| Tool | Version | Check it with | Install |
|---|---|---|---|
| Git | any | `git --version` | https://git-scm.com/downloads |
| Python | **3.10 to 3.13** (3.12 recommended; 3.14 may fail to install OpenCV) | `python3 --version` (Windows: `python --version`) | https://www.python.org/downloads/ or `brew install python@3.12` |
| Node.js (includes npm) | 20 or newer | `node --version` and `npm --version` | https://nodejs.org or `brew install node` |

### Step 1. Download the project
```bash
git clone https://github.com/ItsTheBegginer/RingCareAI.git      # use this repository's URL
cd RingCareAI
```

### Step 2. Install the backend dependencies (terminal 1, from the project root)
The Python dependency list is `requirements.txt` in the project root.
```bash
cd RingCareAI                      # the project root (skip if you are already there)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
cp backend/.env.example backend/.env       # Windows: copy backend\.env.example backend\.env
```
`pip install` installs FastAPI, Uvicorn, OpenCV, boto3 and the other Python packages. OpenCV is large, so this can take a few minutes.
You do not need to edit `backend/.env` for this quickstart.

Check the installation (your prompt should start with `(.venv)`):
```bash
python -c "import fastapi, cv2, boto3; print('backend dependencies OK')"
```

### Step 3. Start the backend (terminal 1, venv still active)
The backend must be started from inside the `backend` folder.
```bash
cd backend
STORAGE_BACKEND=sqlite VISION_BACKEND=opencv NOTIFY_CHANNELS= python -m uvicorn app.main:app --port 8000
```
Windows PowerShell, instead of the last line:
```powershell
$env:STORAGE_BACKEND="sqlite"; $env:VISION_BACKEND="opencv"; $env:NOTIFY_CHANNELS=""; python -m uvicorn app.main:app --port 8000
```
These settings use local storage and the local OpenCV detector, so no cloud services are needed.
You should see `Uvicorn running on http://127.0.0.1:8000`. Check http://localhost:8000/api/health in a browser: it should show `"ok": true`.
Leave this terminal running.

### Step 4. Install the dashboard dependencies and start it (terminal 2, project root)
The dashboard dependency list is `package.json` in the project root (not in `backend`).
```bash
cd RingCareAI                      # the project root, NOT the backend folder
npm install
npm run dev
```
`npm install` downloads React, Vite and the other dashboard packages into `node_modules/`.
You should see `Local: http://localhost:3000/`. Open **http://localhost:3000** in your browser. Leave this terminal running.

### Step 5. Analyse the test clips (terminal 3, any folder)
Each command analyses one clip and adds an event to the dashboard. It appears live, or refresh the page.
Clip names are case-sensitive. Each clip takes a few seconds.

```bash
curl -s -X POST http://localhost:8000/api/events/simulate -H "Content-Type: application/json" -d '{"video": "fall1.mp4"}'
curl -s -X POST http://localhost:8000/api/events/simulate -H "Content-Type: application/json" -d '{"video": "fall2.mp4"}'
curl -s -X POST http://localhost:8000/api/events/simulate -H "Content-Type: application/json" -d '{"video": "fall3.mp4"}'
curl -s -X POST http://localhost:8000/api/events/simulate -H "Content-Type: application/json" -d '{"video": "Ring1.mp4"}'
```
Or all four at once (macOS / Linux):
```bash
for f in fall1 fall2 fall3 Ring1; do curl -s -X POST http://localhost:8000/api/events/simulate -H "Content-Type: application/json" -d "{\"video\": \"$f.mp4\"}" > /dev/null && echo "analysed $f"; done
```
Windows PowerShell (use `curl.exe`, not `curl`):
```powershell
foreach ($f in "fall1","fall2","fall3","Ring1") { curl.exe -s -X POST http://localhost:8000/api/events/simulate -H "Content-Type: application/json" -d "{\`"video\`": \`"$f.mp4\`"}"; echo "analysed $f" }
```

### Step 6. Look at the results on the dashboard
Click an event. You get the playable clip, the analysed frame with a detection box, the evidence behind the priority
(low / medium / high), the limitations and a recommended action. You can **Acknowledge** or **Dismiss** it.

| Clip | What it is | Source |
|---|---|---|
| `fall1.mp4`, `fall2.mp4`, `fall3.mp4` | Stock footage of a people with weapons | Pexels,  **Not Ring footage.** |
| `Ring1.mp4` | A short clip downloaded from the Ring Developer Playground (synthetic sandbox event) | Ring sandbox |

Events analysed this way are labelled **simulated**, including `Ring1.mp4`, because they are read from a file and not
fetched live from Ring. The live Ring flow is described in the full setup below and shown in the demo video.

**About the results.** Without AWS credentials the app uses a basic local person detector (OpenCV), which is weaker than
Amazon Rekognition and can miss people, so results can differ from the demo video, which uses Rekognition.
Our results on these clips with the full setup:



### Stop everything
Press `Ctrl+C` in the backend and dashboard terminals.

### Troubleshooting
- `No module named app`: start the backend from inside the `backend` folder.
- `No module named fastapi` (or `cv2`): the virtual environment is not active, or step 2 did not finish. From the project root run `source .venv/bin/activate` and `pip install -r requirements.txt` again.
- `vite: command not found`: run `npm install` in the project root.
- `npm install` fails with `ERESOLVE`: run `npm install --legacy-peer-deps`.
- OpenCV fails to install: use Python 3.12.
- `No clip named ... in backend/clips`: check the exact file name, including capital letters.
- No events on the page: open http://localhost:8000/api/events and check the backend terminal for errors.
- Port already in use: stop the other program using port 8000 or 3000.

---

## Full setup with Ring and AWS

Do the quickstart steps 0 to 2 and 4 first (backend and dashboard dependencies), then follow these.

### Getting clips from Ring
1. In the Ring Developer Playground, copy the access token (valid about 30 minutes) into `backend/.env` as `RING_ACCESS_TOKEN`.
   You can also swap it without restarting:
   `curl -X POST localhost:8000/api/ring/token -H "Content-Type: application/json" -d '{"access_token":"..."}'`
2. In the Playground, simulate a live-view or motion event.
3. Start the backend (quickstart step 3, but without the three setting overrides) and the dashboard, then click **Fetch Ring Events**.
   The backend lists the device's events, downloads each clip (`POST /v1/devices/{id}/media/video/download`),
   runs the analysis, stores it and pushes it to the dashboard live.

Optional: `RING_POLL_SECONDS=30` polls automatically. A webhook endpoint exists at `/api/webhooks/ring`
(it needs a public HTTPS URL; set `RING_HMAC_KEY`).
If Ring has no downloadable clip for an event and `RING_SAMPLE_FALLBACK=true`, the backend analyses a local sample clip and
labels the event "Ring clip unavailable - analysed a local SAMPLE clip".

### AWS
Install the AWS CLI and run `aws configure`. Then in `backend/.env` set `STORAGE_BACKEND=dynamodb`,
`VISION_BACKEND=rekognition`, `AWS_REGION` and `SNS_TOPIC_ARN`. Create the tables from the `backend` folder:
```bash
python scripts/create_tables.py
```
Permissions needed: DynamoDB (PutItem, GetItem, UpdateItem, DeleteItem, Query), `rekognition:DetectLabels`, `sns:Publish`.
Never commit `.env`.

---

### Run the automated tests (optional)
From the project root, with the virtual environment active:
```bash
pip install -r requirements-dev.txt
PYTHONPATH=backend python -m pytest backend/tests/ -v
```

---

## How it works
Ring event -> backend downloads the clip -> OpenCV picks frames and detects motion -> Amazon Rekognition detects people and
weapon-like objects -> a transparent rules engine (no LLM; see `backend/app/assess.py`) sets the priority and writes the
evidence -> DynamoDB stores it -> alerts (browser, Amazon SNS email, reminders) -> React dashboard.

The Ring integration is in `backend/app/ring.py` (devices, device status, event history, video download), and
`backend/app/pipeline.py` turns each Ring event into a clip, an analysis and a stored assessment.

## Limitations
No live video (recorded clips only) - no medical diagnosis - no contacting of emergency services - no guaranteed fall or
weapon detection - Ring media is watermarked and the sandbox produces synthetic events - Playground tokens expire quickly -
SMS alerts may not work in India - no user accounts.

## Test footage credits
`fall1.mp4`, `fall2.mp4`, `fall3.mp4`: pexels , used under the Pexels license; not Ring footage.
`Ring1.mp4`: downloaded from the Ring Developer Playground.

## License
[MIT] - see `LICENSE`.
