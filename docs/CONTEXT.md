### Manifest AI – Context & Current Status

- **Purpose**: Upload a selfie + a text goal; generate a short video visualizing the user achieving it.
- **MVP duration**: 4 seconds (later 17–20s depending on model limits).
- **Monetization**: $1 per manifestation (add later).
- **Stack**: React (Vite, TS) + FastAPI (Python), SQLite later, local storage now.
- **Provider**: Primary via Replicate (image→video); fallback local MoviePy mock if no token.
- **Key metric**: **TTI (Time-To-Iterate)** — optimize for fastest loop: change -> test -> observe.

### Current Status

- Backend FastAPI ready with endpoints:
  - `POST /api/generations` — upload `file` (jpeg/png, <=8MB) + `prompt`
  - `GET /api/generations/{id}` — status + `video_url` (external) or local stream URL
  - `GET /api/generations/{id}/video` — local MP4 stream (mock path)
  - `GET /api/generations/{id}/image` — original image
- Replicate integration available (uses `REPLICATE_API_TOKEN` and `REPLICATE_MODEL`), otherwise falls back to MoviePy mock.

### Quickstart (Backend)

- Env (Replicate optional):
  - `export REPLICATE_API_TOKEN=...`
  - `export REPLICATE_MODEL="<your-image-to-video-model>"` (pick a suitable model on [Replicate](https://replicate.com/))
- Run:
  - `source .venv/bin/activate`
  - `uvicorn backend/app/main:app --reload --host 0.0.0.0 --port 8000`
- Test (cURL):
  - `curl -F "file=@/path/to/selfie.jpg" -F "prompt=skateboarding a half-pipe" http://localhost:8000/api/generations`
  - Poll `GET /api/generations/{id}` until `succeeded`, then open `video_url` (external) or `GET /api/generations/{id}/video` (mock).

### Next Steps (MVP, ordered for TTI)

1) Scaffold React app in `frontend/` (Vite + TS)
2) Minimal upload form: selfie + prompt -> POST, then poll -> show video (or link) when ready
3) Client-side checks: jpeg/png, <=8MB; show clear errors
4) Tighten backend validation (size cap enforcement)
5) Persistence (SQLite) — replace in-memory dict so jobs survive restarts
6) Provider interface refinement to support different Replicate models

### Notes for Provider via Replicate

- Choose an image→video model on [Replicate](https://replicate.com/) and set `REPLICATE_MODEL` accordingly. Inputs vary by model; our code expects keys `image` and `prompt`. Adjust later per chosen model.
- If no token/model set, the system will generate a 4s local mock video for quick iteration.

### TTI Guidance

- Keep video short (4s) for fast runs.
- Start with mock (no token) to verify UI quickly, then switch to Replicate.
- Defer non-essential polish (styling, DB migrations) until upload->playback loop is stable.
