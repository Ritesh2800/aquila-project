"""All settings in one place. Override with environment variables."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent

DATA_DIR = Path(os.getenv("AQUILA_DATA", BACKEND_DIR / "data"))
VIDEOS_DIR = DATA_DIR / "videos"      # uploaded videos
OUTPUTS_DIR = DATA_DIR / "outputs"    # annotated result videos
ALERTS_DIR = DATA_DIR / "alerts"      # alert clips + snapshots
DB_PATH = DATA_DIR / "alerts.db"
for _d in (VIDEOS_DIR, OUTPUTS_DIR, ALERTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CAMERA_NAME = os.getenv("AQUILA_CAMERA", "CAM-01 (demo)")
OBJ_WEIGHTS  = os.getenv("AQUILA_OBJ_WEIGHTS",  "yolo26x.pt")
POSE_WEIGHTS = os.getenv("AQUILA_POSE_WEIGHTS", "yolo26x-pose.pt")

# Learned fight classifier (.joblib produced by aquila_fight_classifier_training notebook)
FIGHT_MODEL_PATH = os.getenv("AQUILA_FIGHT_MODEL", str(BACKEND_DIR / "aquila_fight_clf.joblib"))
FIGHT_PROB_THR   = float(os.getenv("AQUILA_FIGHT_PROB_THR", "0.6"))   # smoothed prob threshold
FIGHT_SMOOTH     = float(os.getenv("AQUILA_FIGHT_SMOOTH",   "0.6"))   # EMA weight for newest window

# GPU half-precision (FP16): faster on CUDA, ignored on CPU
USE_HALF = os.getenv("AQUILA_USE_HALF", "1") not in ("0", "false", "no")

# Zero-DCE++ (cloned by setup.sh)
ZD_DIR = Path(os.getenv("ZDCE_DIR", PROJECT_DIR / "Zero-DCE_extension" / "Zero-DCE++"))
ZD_SCALE = 1          # 1 = best quality. Try 2 or 4 if it is too slow.
ZD_OUT_INDEX = None   # None = pick automatically. If the result looks wrong, try 0 or 1.

# ---- scoring settings (same guesses as the notebook - tune on your own clips) ----
WEAPON_NAMES = {"knife"}
PERSON_NAMES = {"person", "people"}
DARK_ON, DARK_OFF = 60, 80
FIGHT_SPEED = 2.5
BUFFER_S = 8
CUE_FRAMES = 8
WEIGHTS = dict(weapon_near=0.50, weapon=0.25, fight=0.65, lying=0.15, hands_up=0.10)  # fight raised 0.35→0.65 so fight alone clears 0.6 threshold

# ---- alert retention ----
HOURS_UNCONFIRMED = 24
DAYS_CONFIRMED = 7

# ---- notifications (replaces Colab userdata) ----
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ---- Twilio voice/SMS alerts ----
TWILIO_SID   = os.getenv("TWILIO_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN", "")
TWILIO_FROM  = os.getenv("TWILIO_FROM", "")
TWILIO_TO    = os.getenv("TWILIO_TO", "")


# ---- server ----
API_KEY = os.getenv("AQUILA_API_KEY", "")   # empty = no login (fine for local use only)
CORS_ORIGINS = [o for o in os.getenv("AQUILA_CORS", "http://localhost:5173").split(",") if o]
MAX_UPLOAD_MB = int(os.getenv("AQUILA_MAX_UPLOAD_MB", "500"))
