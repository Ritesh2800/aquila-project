"""Telegram + Twilio voice/SMS notification helpers."""
import os
import re
import time
from html import escape

import requests
import config

# ── Telegram ──────────────────────────────────────────────────────────────────

def tg_send(text, video_path=None):
    token, chat = config.TELEGRAM_TOKEN, config.TELEGRAM_CHAT_ID
    if not token or not chat:
        return "skipped (no Telegram settings)"
    base = f"https://api.telegram.org/bot{token}"
    try:
        if video_path:
            with open(video_path, "rb") as f:
                r = requests.post(f"{base}/sendVideo", data={"chat_id": chat, "caption": text[:1000]},
                                  files={"video": f}, timeout=90)
        else:
            r = requests.post(f"{base}/sendMessage", data={"chat_id": chat, "text": text}, timeout=30)
        return "sent" if r.ok else f"failed (HTTP {r.status_code})"
    except Exception as e:
        return f"failed ({type(e).__name__})"


# ── Twilio helpers ────────────────────────────────────────────────────────────

TRIAL_VOICE_URL = "https://webhooks.twilio.com/v1/Voice/Template/voice_text_to_speech"
CALL_WAIT_S     = 20   # max seconds to poll for a final status


def _twilio_creds():
    sid   = config.TWILIO_SID
    token = config.TWILIO_TOKEN
    frm   = config.TWILIO_FROM
    to    = config.TWILIO_TO
    for label, val in (("TWILIO_SID", sid), ("TWILIO_TOKEN", token),
                       ("TWILIO_FROM", frm), ("TWILIO_TO", to)):
        if not val:
            raise RuntimeError(f"{label} is not set in .env")
    for label, num in (("TWILIO_FROM", frm), ("TWILIO_TO", to)):
        if not re.fullmatch(r"\+\d{8,15}", num):
            raise RuntimeError(f"{label} must be E.164, e.g. +919876543210 (got '{num}')")
    return sid, token, frm, to


def twilio_available():
    """True when all four Twilio env-vars are present and look valid."""
    try:
        _twilio_creds()
        return True
    except Exception:
        return False


def twilio_call_async(message: str) -> dict:
    """
    Starts a Twilio voice call and returns immediately with the call SID
    and initial status. Use twilio_poll_status() to follow progress.
    """
    from twilio.rest import Client
    sid, token, frm, to = _twilio_creds()
    client = Client(sid, token)

    # On trial the built-in TTS template always works; skip custom TwiML.
    call = client.calls.create(to=to, from_=frm, url=TRIAL_VOICE_URL)
    return {"sid": call.sid, "status": call.status, "to": to, "from": frm}


def twilio_poll_status(call_sid: str) -> dict:
    """Fetch the current status of a call by SID."""
    from twilio.rest import Client
    sid, token, _, _ = _twilio_creds()
    client = Client(sid, token)
    call = client.calls(call_sid).fetch()
    return {"sid": call_sid, "status": call.status}


def twilio_sms(message: str) -> str:
    from twilio.rest import Client
    sid, token, frm, to = _twilio_creds()
    client = Client(sid, token)
    msg = client.messages.create(to=to, from_=frm, body=message[:1600])
    waited = 0
    while waited < CALL_WAIT_S and msg.status in ("queued", "accepted", "sending"):
        time.sleep(2); waited += 2
        msg = client.messages(msg.sid).fetch()
    extra = f" error {msg.error_code}: {msg.error_message}" if msg.error_code else ""
    return f"{msg.status}{extra} ({msg.sid})"


# ── Confirm-alert workflow ────────────────────────────────────────────────────

def notify_helpline(alert):
    """Called when a human clicks Confirm on an alert."""
    reasons = str(alert.get("reasons", [])).replace("_", " ")
    score   = float(alert.get("score", 0))
    text    = (f"Aquila alert #{alert['id']} | {alert['camera']} | "
               f"score {score:.2f} | {reasons} | confirmed by reviewer")

    parts = []

    if twilio_available():
        try:
            result = twilio_call_async(text)
            parts.append(f"call started ({result['status']}, sid={result['sid']})")
        except Exception as e:
            parts.append(f"call FAILED ({type(e).__name__}: {e})")
    else:
        parts.append("Twilio not configured")

    parts.append(f"telegram: {tg_send(text)}")
    return " | ".join(parts)
