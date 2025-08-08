from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4
from datetime import datetime
import os
import shutil

from .services.replicate_provider import ReplicateVideoProvider
from .prompts import enhance_prompt

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(APP_DIR)
ASSETS_DIR = os.path.join(APP_DIR, "assets")
UPLOAD_DIR = os.path.join(ASSETS_DIR, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Manifest AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://manifest-9c49kfzn7-sksareens-projects.vercel.app",
        "https://manifest.vercel.app",  # In case you want a custom domain later
        "https://*.vercel.app",  # All vercel deployments
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

class Generation(BaseModel):
    id: str
    prompt: str
    image_path: str
    status: str
    video_path: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

DB: dict[str, Generation] = {}


def save_upload(file: UploadFile, dest_path: str) -> None:
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

def ensure_replicate_env() -> None:
    if not os.getenv("REPLICATE_API_TOKEN"):
        raise HTTPException(status_code=400, detail="REPLICATE_API_TOKEN is not set on the server")


@app.post("/api/generations")
async def create_generation(background_tasks: BackgroundTasks, file: UploadFile = File(...), prompt: str = Form(...)):
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only JPEG and PNG are supported")

    gen_id = str(uuid4())
    image_ext = ".jpg" if file.content_type == "image/jpeg" else ".png"
    image_path = os.path.join(UPLOAD_DIR, f"{gen_id}{image_ext}")

    save_upload(file, image_path)

    generation = Generation(
        id=gen_id,
        prompt=prompt,
        image_path=image_path,
        status="queued",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    DB[gen_id] = generation

    def task():
        try:
            DB[gen_id].status = "processing"
            DB[gen_id].updated_at = datetime.utcnow()
            provider_token = os.getenv("REPLICATE_API_TOKEN")
            video_model = os.getenv("REPLICATE_MODEL_VIDEO", "bytedance/seedance-1-lite")
            provider = ReplicateVideoProvider(api_token=provider_token, model=video_model)
            enhanced_prompt = enhance_prompt(prompt)
            video_url = provider.generate(image_path, enhanced_prompt)
            DB[gen_id].status = "succeeded"
            DB[gen_id].video_url = video_url
            DB[gen_id].updated_at = datetime.utcnow()
        except Exception as e:
            DB[gen_id].status = "failed"
            DB[gen_id].error = str(e)
            DB[gen_id].updated_at = datetime.utcnow()

    # Fail fast if Replicate is not configured
    ensure_replicate_env()
    background_tasks.add_task(task)

    return {"id": gen_id, "status": generation.status}


@app.get("/api/generations/{gen_id}")
async def get_generation(gen_id: str):
    generation = DB.get(gen_id)
    if not generation:
        raise HTTPException(status_code=404, detail="Not found")

    image_url = None
    if os.path.exists(generation.image_path):
        image_url = f"/api/generations/{gen_id}/image"

    video_url = generation.video_url

    return {
        "id": generation.id,
        "status": generation.status,
        "prompt": generation.prompt,
        "image_url": image_url,
        "video_url": video_url,
        "error": generation.error,
    }


@app.get("/api/generations/{gen_id}/image")
async def get_image(gen_id: str):
    generation = DB.get(gen_id)
    if not generation or not os.path.exists(generation.image_path):
        raise HTTPException(status_code=404, detail="Not found")
    media_type = "image/jpeg" if generation.image_path.endswith(".jpg") else "image/png"
    return FileResponse(generation.image_path, media_type=media_type)


# No local video endpoint in Replicate-only mode


@app.get("/")
async def root():
    return {"ok": True}
