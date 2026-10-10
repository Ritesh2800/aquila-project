"""Aquila API.  Run:  uvicorn main:app --host 0.0.0.0 --port 8000"""
import asyncio
import os
import secrets
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env so Telegram/API-key settings work without manually exporting vars
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import APIRouter, Depends, FastAPI, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
import db

jobs = {}                                   # job_id -> dict
executor = ThreadPoolExecutor(max_workers=1)  # one video at a time: tracker state is shared
ALLOWED_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
startup = {"models_ready": False, "error": ""}


def _warmup():
    """Load the models in the background so the first analysis starts fast."""
    try:
        import enhance
        from models import get_models
        get_models()
        try:
            enhance.get_zdce()
        except Exception as e:           # the app still works without enhancement
            startup["error"] = str(e)
        startup["models_ready"] = True
    except Exception as e:
        startup["error"] = f"Model loading failed: {e}"


async def _cleanup_loop():
    while True:
        await asyncio.sleep(3600)
        await asyncio.to_thread(db.cleanup_old)


@asynccontextmanager
async def lifespan(app):
    db.init()
    threading.Thread(target=_warmup, daemon=True).start()
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()


app = FastAPI(title="Aquila", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])


def require_key(x_api_key: str | None = Header(None), key: str | None = Query(None)):
    if config.API_KEY and not secrets.compare_digest(x_api_key or key or "", config.API_KEY):
        raise HTTPException(401, "Missing or wrong access key")


api = APIRouter(dependencies=[Depends(require_key)])


@app.get("/api/health")
def health():
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        device = "unknown"
    # Check system ffmpeg first, then fall back to bundled imageio-ffmpeg
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    if not ffmpeg_ok:
        try:
            import imageio_ffmpeg
            imageio_ffmpeg.get_ffmpeg_exe()
            ffmpeg_ok = True
        except Exception:
            pass
    return dict(auth_required=bool(config.API_KEY), device=device,
                models_ready=startup["models_ready"], notice=startup["error"],
                ffmpeg=ffmpeg_ok,
                telegram=bool(config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID),
                twilio=bool(config.TWILIO_SID and config.TWILIO_TOKEN and
                            config.TWILIO_FROM and config.TWILIO_TO),
                camera=config.CAMERA_NAME)


@api.get("/api/auth/check")
def auth_check():
    return {"ok": True}


# ---------------------------------------------------------------- Twilio demo call
@api.post("/api/test-call")
def test_call():
    """Start a demo Twilio voice call and return the call SID immediately."""
    from notify import twilio_call_async, twilio_available
    if not twilio_available():
        raise HTTPException(400, "Twilio credentials not configured in .env")
    try:
        result = twilio_call_async(
            "This is a test alert from Aquila, the low-light early warning system. "
            "A danger event has been detected. A human reviewer has confirmed the alert. "
            "Please check the monitored location immediately."
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@api.get("/api/call-status/{call_sid}")
def call_status(call_sid: str):
    """Poll the live status of an ongoing Twilio call."""
    from notify import twilio_poll_status
    try:
        return twilio_poll_status(call_sid)
    except Exception as e:
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------- analysis jobs
def _run_job(job_id, video_path, opts):
    from pipeline import run_pipeline
    job = jobs[job_id]
    job["status"] = "running"

    def progress(i, total):
        job["progress"] = round(min(i / total, 1.0), 3) if total else 0

    try:
        out_path = str(config.OUTPUTS_DIR / f"{job_id}.mp4")
        r = run_pipeline(video_path, out_path, on_progress=progress, **opts)
        r["video_url"] = f"/files/outputs/{os.path.basename(r.pop('video_path'))}"
        job.update(status="done", progress=1.0, result=r)
    except Exception as e:
        job.update(status="error", error=str(e))
    finally:
        try:
            os.remove(video_path)       # keep disk use low: the annotated copy is what we keep
        except OSError:
            pass


@api.post("/api/analyze")
async def analyze(video: UploadFile,
                  enhance_mode: str = Form("auto", pattern="^(auto|on|off)$"),
                  conf: float = Form(0.3, ge=0.05, le=0.95),
                  hold_s: float = Form(4.0, ge=0.5, le=15),
                  score_thr: float = Form(0.6, ge=0.1, le=1.0),
                  max_seconds: int = Form(60, ge=1, le=600),
                  camera: str = Form(config.CAMERA_NAME, max_length=80),
                  send_telegram: bool = Form(False)):
    ext = Path(video.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported file type. Use one of: {', '.join(sorted(ALLOWED_EXT))}")
    job_id = uuid.uuid4().hex[:12]
    path = config.VIDEOS_DIR / f"{job_id}{ext}"
    size, limit = 0, config.MAX_UPLOAD_MB * 1024 * 1024
    with open(path, "wb") as f:
        while chunk := await video.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                f.close()
                path.unlink(missing_ok=True)
                raise HTTPException(413, f"Video is larger than {config.MAX_UPLOAD_MB} MB")
            f.write(chunk)
    jobs[job_id] = dict(id=job_id, status="queued", progress=0.0)
    executor.submit(_run_job, job_id, str(path),
                    dict(enhance_mode=enhance_mode, conf=conf, hold_s=hold_s, score_thr=score_thr,
                         max_seconds=max_seconds, camera=camera, send_telegram=send_telegram))
    return jobs[job_id]


@api.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Unknown job")
    return jobs[job_id]


# ---------------------------------------------------------------- alerts
@api.get("/api/alerts")
def alerts(status: str | None = None):
    return db.list_alerts(status)


@api.get("/api/alerts/{alert_id}")
def alert(alert_id: int):
    a = db.get_alert(alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    return a


@api.post("/api/alerts/{alert_id}/confirm")
def confirm(alert_id: int):
    from notify import notify_helpline
    a = db.get_alert(alert_id)
    if not a:
        raise HTTPException(404, "Alert not found")
    db.set_status(alert_id, "confirmed")
    return {"message": "Confirmed. " + notify_helpline(a)}


@api.post("/api/alerts/{alert_id}/dismiss")
def dismiss(alert_id: int):
    if not db.get_alert(alert_id):
        raise HTTPException(404, "Alert not found")
    db.set_status(alert_id, "dismissed")
    return {"message": "Dismissed. No call made."}


@api.post("/api/cleanup")
def cleanup():
    return {"message": f"Deleted {db.cleanup_old()} old alert(s)."}


# ---------------------------------------------------------------- media files
@api.get("/files/{kind}/{name}")
def files(kind: str, name: str):
    folder = {"outputs": config.OUTPUTS_DIR, "alerts": config.ALERTS_DIR}.get(kind)
    path = folder / Path(name).name if folder else None
    if not path or not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path)


app.include_router(api)

# If the frontend has been built (npm run build), serve it from the same server.
_dist = config.PROJECT_DIR / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
