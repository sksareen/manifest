from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4
from datetime import datetime
import os
import shutil

from moviepy.editor import ImageClip
from .services.replicate_provider import ReplicateVideoProvider

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(APP_DIR)
ASSETS_DIR = os.path.join(APP_DIR, "assets")
UPLOAD_DIR = os.path.join(ASSETS_DIR, "uploads")
VIDEO_DIR = os.path.join(ASSETS_DIR, "videos")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

app = FastAPI(title="Manifest AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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


def generate_mock_video(image_path: str, output_path: str, duration: float = 4.0) -> None:
    clip = ImageClip(image_path).set_duration(duration)
    # Simple Ken Burns effect: zoom from 1.0 to 1.1 over duration
    def zoom(t):
        scale = 1.0 + 0.1 * (t / duration)
        return scale
    w, h = clip.size
    fx = clip.resize(lambda t: zoom(t))
    # Center crop to original size to avoid borders
    fx = fx.crop(x_center=w/2, y_center=h/2, width=w, height=h)
    fx.write_videofile(output_path, fps=24, codec="libx264", audio=False, verbose=False, logger=None)


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

    output_path = os.path.join(VIDEO_DIR, f"{gen_id}.mp4")

    def task():
        try:
            DB[gen_id].status = "processing"
            DB[gen_id].updated_at = datetime.utcnow()
            provider_token = os.getenv("REPLICATE_API_TOKEN")
            if provider_token:
                provider = ReplicateVideoProvider(api_token=provider_token)
                video_url = provider.generate(image_path, prompt)
                DB[gen_id].status = "succeeded"
                DB[gen_id].video_url = video_url
            else:
                generate_mock_video(image_path, output_path, duration=4.0)
                DB[gen_id].status = "succeeded"
                DB[gen_id].video_path = output_path
            DB[gen_id].updated_at = datetime.utcnow()
        except Exception as e:
            DB[gen_id].status = "failed"
            DB[gen_id].error = str(e)
            DB[gen_id].updated_at = datetime.utcnow()

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
    if generation.video_path and os.path.exists(generation.video_path):
        video_url = f"/api/generations/{gen_id}/video"

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


@app.get("/api/generations/{gen_id}/video")
async def get_video(gen_id: str):
    generation = DB.get(gen_id)
    if not generation or not generation.video_path or not os.path.exists(generation.video_path):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(generation.video_path, media_type="video/mp4")


@app.get("/")
async def root():
    return {"ok": True}
