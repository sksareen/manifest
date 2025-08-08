### Backend (FastAPI)

Run dev server:

```
source ../../.venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Test with curl:

```
curl -F "file=@/path/to/selfie.jpg" -F "prompt=skateboarding a half-pipe" http://localhost:8000/api/generations
```
