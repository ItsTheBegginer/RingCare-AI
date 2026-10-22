# Friction log - RingCare AI



## 1. Downloaded Ring clip would not play in the browser
- **Task:** play a clip downloaded through the Ring video download endpoint in the dashboard's video player.
- **Steps:** downloaded the MP4, saved it, served it to an HTML video element.
- **Expected:** the clip plays.
- **Actual:** the player spun forever and never played, while the OpenCV analysis of the same file succeeded. 
- **Severity:** Medium.
- **Workaround:** re-encode every clip to WebM with OpenCV and serve that; keep the original.
- **Suggestion:** document the codec and container of media downloads, or offer a browser-playable rendition.

## 2. Playground access token expires after about 30 minutes
- **Task:** keep the backend polling and fetching events during a testing session.
- **Steps:** pasted the Playground token into the backend, left it running, restarted it during development.
- **Expected:** a token that lasts through a session, or an obvious refresh path.
- **Actual:** calls started failing after about 30 minutes, and a token sent at runtime was lost on restart.
- **Severity:** Medium.
- **Workaround:** a runtime endpoint to swap the token, a clear "token expired" status, and instructions to paste a fresh one.
- **Suggestion:** longer-lived Playground tokens, or a documented refresh flow for the Playground.

## 3. The sandbox produces only synthetic events
- **Task:** show realistic incident detection (a person on the floor, a weapon-like object) using Playground events.
- **Steps:** triggered Playground events and downloaded their clips.
- **Expected:** sample scenarios that resemble real situations.
- **Actual:** synthetic events with low-priority content, which cannot demonstrate caretaking or security detection.
- **Severity:** Medium.
- **Workaround:** staged and licensed stock clips, clearly labelled as simulated and not Ring footage.
- **Suggestion:** labelled sample scenarios in the Playground (person walking, lying down, a package).

## 4. OpenCV failed to start on Python 3.14 
- **Task:** start the backend in a new virtual environment.
- **Steps:** created the environment with Python 3.14 and installed the requirements.
- **Expected:** the OpenCV person detector initialises.
- **Actual:** the server crashed on start while creating the OpenCV detector.
- **Severity:** Low.
- **Workaround:** use Python 3.12, and create the detector lazily so a failure cannot stop startup.
- **Suggestion:** document the supported Python versions.
