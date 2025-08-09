from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4
from datetime import datetime, timedelta
import os
import shutil
import json
from dotenv import load_dotenv

from .services.replicate_provider import ReplicateVideoProvider
from .prompts import enhance_prompt
from .services.video_utils import download_to, extract_last_frame, merge_two_with_xfade, trim_video

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(APP_DIR)
ASSETS_DIR = os.path.join(APP_DIR, "assets")
UPLOAD_DIR = os.path.join(ASSETS_DIR, "uploads")
VIDEOS_DIR = os.path.join(ASSETS_DIR, "videos")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)

app = FastAPI(title="Manifest AI")

# Load environment from .env for local/dev runs (production uses platform secrets)
load_dotenv()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=False,  # Must be False when allow_origins is "*"
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class Generation(BaseModel):
    id: str
    prompt: str
    image_path: str
    status: str
    video_path: Optional[str] = None
    video_url: Optional[str] = None
    final_video_path: Optional[str] = None
    final_video_url: Optional[str] = None
    segments: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    progress_stage: Optional[str] = None
    estimated_completion: Optional[datetime] = None
    estimated_remaining_seconds: Optional[int] = None

DB: dict[str, Generation] = {}
PAID_SESSIONS: set[str] = set()
CONSUMED_SESSIONS: set[str] = set()


def save_upload(file: UploadFile, dest_path: str) -> None:
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

def ensure_replicate_env() -> None:
    if not os.getenv("REPLICATE_API_TOKEN"):
        raise HTTPException(status_code=400, detail="REPLICATE_API_TOKEN is not set on the server")


@app.post("/api/generations")
async def create_generation(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    prompt: str = Form(...),
    session_id: Optional[str] = Form(None),
    mode: Optional[str] = Form("preview"),  # 'preview' | 'full'
):
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only JPEG and PNG are supported")

    gen_id = str(uuid4())
    image_ext = ".jpg" if file.content_type == "image/jpeg" else ".png"
    image_path = os.path.join(UPLOAD_DIR, f"{gen_id}{image_ext}")

    save_upload(file, image_path)

    # Optional Stripe enforcement
    stripe_enforce = os.getenv("STRIPE_ENFORCE", "0") not in ("0", "false", "False", None)
    if stripe_enforce and mode == "full":
        if not session_id:
            raise HTTPException(status_code=402, detail="Payment required: missing session_id")
        if session_id in CONSUMED_SESSIONS:
            raise HTTPException(status_code=402, detail="Payment session already used")
        if session_id not in PAID_SESSIONS:
            # Best-effort live verify via Stripe if configured
            try:
                import stripe
                sk = os.getenv("STRIPE_SECRET_KEY")
                if not sk:
                    raise HTTPException(status_code=500, detail="Stripe not configured on server")
                stripe.api_key = sk
                sess = stripe.checkout.Session.retrieve(session_id)
                if sess and sess.get("payment_status") == "paid":
                    PAID_SESSIONS.add(session_id)
                else:
                    raise HTTPException(status_code=402, detail="Payment not completed")
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=402, detail="Payment not verified")

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
            start_time = datetime.utcnow()
            
            # Initial setup with ETA
            DB[gen_id].status = "processing"
            DB[gen_id].progress_stage = "Initializing video generation..."
            DB[gen_id].estimated_remaining_seconds = 120  # Initial estimate: 2 minutes
            DB[gen_id].estimated_completion = start_time + timedelta(seconds=120)
            DB[gen_id].updated_at = start_time
            
            provider_token = os.getenv("REPLICATE_API_TOKEN")
            video_model = (
                os.getenv("REPLICATE_MODEL_VIDEO_PREVIEW", "bytedance/seedance-1-lite")
                if mode == "preview"
                else os.getenv("REPLICATE_MODEL_VIDEO", "bytedance/seedance-1-pro")
            )
            provider = ReplicateVideoProvider(api_token=provider_token, model=video_model)
            enhanced_prompt = enhance_prompt(prompt)

            fps = int(os.getenv("VIDEO_FPS", "24"))
            seg_seconds = (
                5 if mode == "preview" else int(os.getenv("VIDEO_SEGMENT_SECONDS", "10"))
            )
            # Enforce model-specific allowed durations to avoid 422s
            if "bytedance/seedance-1-pro" in video_model and seg_seconds not in (5, 10):
                seg_seconds = 10
            xfade_sec = float(os.getenv("CROSSFADE_SECONDS", "0.9"))
            width = int(os.getenv("VIDEO_WIDTH", "720"))

            work_dir = os.path.join(VIDEOS_DIR, gen_id)
            os.makedirs(work_dir, exist_ok=True)

            # Segment 1 (seeded by uploaded image) - duration depends on mode
            DB[gen_id].progress_stage = "Generating first video segment..."
            DB[gen_id].estimated_remaining_seconds = 100
            DB[gen_id].estimated_completion = datetime.utcnow() + timedelta(seconds=100)
            DB[gen_id].updated_at = datetime.utcnow()
            
            seg1_url = provider.generate(image_path, enhanced_prompt, extra_inputs={"duration": seg_seconds, "fps": fps})
            seg1_path = os.path.join(work_dir, "seg1.mp4")
            download_to(seg1_path, seg1_url)

            # If preview mode: return a 3s trimmed clip
            if mode == "preview":
                preview_seconds = float(os.getenv("PREVIEW_SECONDS", "3"))
                preview_width = int(os.getenv("PREVIEW_WIDTH", "480"))
                final_path = os.path.join(work_dir, "preview.mp4")
                trim_video(seg1_path, final_path, duration_seconds=preview_seconds, fps=fps, width=preview_width)

                DB[gen_id].status = "succeeded"
                DB[gen_id].progress_stage = "Preview ready"
                DB[gen_id].estimated_remaining_seconds = 0
                DB[gen_id].final_video_path = final_path
                DB[gen_id].final_video_url = f"/api/generations/{gen_id}/video"
                DB[gen_id].video_url = DB[gen_id].final_video_url
                DB[gen_id].segments = 1
                DB[gen_id].updated_at = datetime.utcnow()
                return

            # Segment 2 (seeded by last frame of seg1 for continuity)
            DB[gen_id].progress_stage = "Processing frame transition..."
            DB[gen_id].estimated_remaining_seconds = 75
            DB[gen_id].estimated_completion = datetime.utcnow() + timedelta(seconds=75)
            DB[gen_id].updated_at = datetime.utcnow()
            
            last_frame_path = os.path.join(work_dir, "seg1_last.jpg")
            extract_last_frame(seg1_path, last_frame_path)
            
            DB[gen_id].progress_stage = "Generating second video segment..."
            DB[gen_id].estimated_remaining_seconds = 70
            DB[gen_id].estimated_completion = datetime.utcnow() + timedelta(seconds=70)
            DB[gen_id].updated_at = datetime.utcnow()
            
            seg2_url = provider.generate(last_frame_path, enhanced_prompt, extra_inputs={"duration": seg_seconds, "fps": fps})
            seg2_path = os.path.join(work_dir, "seg2.mp4")
            download_to(seg2_path, seg2_url)

            # Merge with crossfade for seamless transition - Usually takes 10-20 seconds
            DB[gen_id].progress_stage = "Merging video segments..."
            DB[gen_id].estimated_remaining_seconds = 15
            DB[gen_id].estimated_completion = datetime.utcnow() + timedelta(seconds=15)
            DB[gen_id].updated_at = datetime.utcnow()
            
            final_path = os.path.join(work_dir, "final.mp4")
            merge_two_with_xfade(seg1_path, seg2_path, final_path, xfade_sec=xfade_sec, fps=fps, width=width)

            DB[gen_id].status = "succeeded"
            DB[gen_id].progress_stage = "Completed"
            DB[gen_id].estimated_remaining_seconds = 0
            DB[gen_id].final_video_path = final_path
            DB[gen_id].final_video_url = f"/api/generations/{gen_id}/video"
            # Preserve existing frontend contract
            DB[gen_id].video_url = DB[gen_id].final_video_url
            DB[gen_id].segments = 2
            DB[gen_id].updated_at = datetime.utcnow()

            # Mark session consumed if enforced
            if stripe_enforce and session_id:
                CONSUMED_SESSIONS.add(session_id)
        except Exception as e:
            DB[gen_id].status = "failed"
            DB[gen_id].error = str(e)
            DB[gen_id].progress_stage = "Failed"
            DB[gen_id].estimated_remaining_seconds = 0
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
        "progress_stage": generation.progress_stage,
        "estimated_remaining_seconds": generation.estimated_remaining_seconds,
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
    if not generation or not generation.final_video_path or not os.path.exists(generation.final_video_path):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(generation.final_video_path, media_type="video/mp4")


@app.get("/")
async def root():
    return {"ok": True}


# -------- Stripe minimal API --------

def _public_site_url() -> str:
    return os.getenv("PUBLIC_SITE_URL", "http://localhost:5173")


@app.post("/api/payments/create-session")
async def create_checkout_session(request: Request):
    try:
        import stripe
    except Exception:
        raise HTTPException(status_code=500, detail="Stripe SDK not installed")

    sk = os.getenv("STRIPE_SECRET_KEY")
    price_id = os.getenv("STRIPE_PRICE_ID")
    site = _public_site_url().rstrip("/")
    if not sk:
        raise HTTPException(status_code=500, detail="Stripe not configured on server")

    stripe.api_key = sk
    try:
        # Resolve price by lookup key if provided
        if not price_id:
            lookup_key = os.getenv("STRIPE_PRICE_LOOKUP_KEY")
            if lookup_key:
                pr = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
                if pr and pr.data:
                    price_id = pr.data[0].id

        # Resolve price via product id if provided
        if not price_id:
            product_id = os.getenv("STRIPE_PRODUCT_ID")
            if product_id:
                try:
                    product = stripe.Product.retrieve(product_id, expand=["default_price"])
                    dp = product.get("default_price")
                    if isinstance(dp, dict) and dp.get("id"):
                        price_id = dp["id"]
                    elif isinstance(dp, str):
                        price_id = dp
                except Exception:
                    price_id = None
                if not price_id:
                    prices = stripe.Price.list(product=product_id, active=True, limit=1)
                    if prices and prices.data:
                        price_id = prices.data[0].id
                if not price_id:
                    # Create a one-off price for this product using fallback amount
                    amount_cents = int(os.getenv("STRIPE_AMOUNT_CENTS", "999"))
                    currency = os.getenv("STRIPE_CURRENCY", "usd")
                    created = stripe.Price.create(unit_amount=amount_cents, currency=currency, product=product_id)
                    price_id = created.id

        # Build line items
        if price_id:
            line_items = [{"price": price_id, "quantity": 1}]
        else:
            # Fallback inline price
            amount_cents = int(os.getenv("STRIPE_AMOUNT_CENTS", "999"))
            currency = os.getenv("STRIPE_CURRENCY", "usd")
            product_name = os.getenv("STRIPE_PRODUCT_NAME", "20s HD Video")
            line_items = [{
                "price_data": {
                    "currency": currency,
                    "unit_amount": amount_cents,
                    "product_data": {"name": product_name},
                },
                "quantity": 1,
            }]

        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            success_url=f"{site}/?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{site}/?checkout=cancelled",
            automatic_tax={"enabled": False},
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {e}")


@app.post("/api/payments/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="Stripe webhook not configured")
    try:
        import stripe
        event = stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook signature verification failed: {e}")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        sid = session.get("id")
        if sid:
            PAID_SESSIONS.add(sid)
    return {"received": True}
