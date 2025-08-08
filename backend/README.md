### Backend (FastAPI)

Quick run options:

- Easiest (reload by default):
  ```
  source ../.venv/bin/activate
  cd backend
  python main.py
  ```

- Uvicorn directly:
  ```
  source ../.venv/bin/activate
  cd backend
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```

Env (optional for Replicate):
```
export REPLICATE_API_TOKEN=... 
export REPLICATE_MODEL="<image-to-video-model>"
```

Test with curl:

```
curl -F "file=@/path/to/selfie.jpg" -F "prompt=skateboarding a half-pipe" http://localhost:8000/api/generations
```
