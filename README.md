# Aquila: low-light early warning

The notebook, split into a **FastAPI backend** and a **React frontend**.

```
backend/   config.py  scoring.py  enhance.py  models.py  pipeline.py  db.py  notify.py  main.py
frontend/  src/App.jsx  Analyse.jsx  Alerts.jsx  ScoreChart.jsx  api.js  styles.css
```

## Requirements
Python 3.10+, Node 18+, ffmpeg, git. An NVIDIA GPU is strongly recommended
(two YOLOv8m models plus Zero-DCE++ are slow on CPU).

## Run it
```bash
./setup.sh        # once: venv, Python packages, Zero-DCE++ repo, npm packages
./run_dev.sh      # open http://localhost:5173
```
The first start downloads `yolov8m.pt` and `yolov8m-pose.pt`. The sidebar shows "Models ready" when loading finishes.

Single-server mode (what you would deploy): `./run_prod.sh`, then open http://localhost:8000.

## Settings (environment variables)
See `.env.example`. Telegram and the access key replace the Colab `userdata` secrets and the open Gradio link.

| Variable | Purpose |
|---|---|
| `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` | Telegram alerts and the sandbox helpline message |
| `AQUILA_API_KEY` | Turns on a login screen. **Set this before exposing the server beyond your own machine.** |
| `AQUILA_DATA` | Where videos, alert clips and the database are stored |
| `AQUILA_MAX_UPLOAD_MB` | Upload limit (default 500) |

Scoring weights, thresholds and retention times are in `backend/config.py`.

## API
| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Device, model status, whether login is required |
| `POST /api/analyze` | Upload a video and settings, returns a job |
| `GET /api/jobs/{id}` | Progress, then result (video URL, events, score series) |
| `GET /api/alerts` | All alerts (`?status=pending`) |
| `POST /api/alerts/{id}/confirm` / `dismiss` | Human review |
| `POST /api/cleanup` | Delete expired alerts |

Interactive docs: http://localhost:8000/docs

## Notes
- Videos are analysed **one at a time** (a queue), because the tracker state is shared.
- Uploaded originals are deleted after analysis; the annotated video and alert clips are kept until cleanup (24 h unconfirmed, 7 days confirmed, hourly).
- `notify_helpline` in `backend/notify.py` is still the sandbox from your notebook. Add Twilio there.
- Running the backend in Colab for testing: install the requirements, run uvicorn in a background thread, and expose port 8000 with ngrok or cloudflared. Colab sessions are temporary, so it is not for production.
