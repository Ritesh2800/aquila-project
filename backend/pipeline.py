"""The detection pipeline from the notebook, as a plain function that reports progress."""
import os
import shutil
import subprocess
import time
from collections import deque
from datetime import datetime

import cv2
import numpy as np

import config
import db
import enhance
from models import get_models
from notify import tg_send
from scoring import (AlertGate, L_WR, R_WR, danger_score, fight_like, hands_up, lying,
                     weapon_near_person)

FONT = cv2.FONT_HERSHEY_SIMPLEX


def _ffmpeg():
    """Return path to ffmpeg binary: system install first, then bundled imageio-ffmpeg."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise RuntimeError(
            "ffmpeg not found. Install it or run: pip install imageio-ffmpeg"
        )


def _to_h264(src, dst):
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-i", src, "-vcodec", "libx264",
                    "-pix_fmt", "yuv420p", dst], check=True)


def write_clip(frames, fps, path):
    if not frames:
        return None
    h, w = frames[0].shape[:2]
    tmp = path.replace(".mp4", "_raw.mp4")
    wr = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        wr.write(f)
    wr.release()
    _to_h264(tmp, path)
    os.remove(tmp)
    return path


def draw_hud(img, score, progress, hold_s, thr, reasons, enhanced):
    H, W = img.shape[:2]
    bw = max(int(W * 0.30), 120)
    cv2.rectangle(img, (10, 10), (10 + bw, 30), (50, 50, 50), -1)
    color = (0, 0, 255) if score >= thr else (0, 200, 0)
    cv2.rectangle(img, (10, 10), (10 + int(bw * min(score, 1.0)), 30), color, -1)
    tx = 10 + int(bw * thr)
    cv2.line(img, (tx, 6), (tx, 34), (255, 255, 255), 2)
    text = f"danger {score:.2f}"
    if progress > 0:
        text += f" | holding {progress * hold_s:.1f}/{hold_s:.0f}s"
    cv2.putText(img, text, (10, 54), FONT, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    if reasons:
        cv2.putText(img, ", ".join(reasons), (10, 78), FONT, 0.55, (0, 255, 255), 2, cv2.LINE_AA)
    tag = "Zero-DCE++ ON" if enhanced else "enhancement off"
    cv2.putText(img, tag, (10, H - 12), FONT, 0.55, (255, 255, 0) if enhanced else (200, 200, 200), 2, cv2.LINE_AA)


def run_pipeline(video_path, out_path, conf=0.3, imgsz=640, enhance_mode="auto", hold_s=4.0,
                 score_thr=0.6, camera=config.CAMERA_NAME, max_seconds=60, send_telegram=False,
                 on_progress=None):
    """Returns a dict: video_path, events, series, n_alerts, speed, enhanced_fraction, warnings."""
    obj_model, pose_model, obj_ids = get_models()
    obj_model.predictor = None     # reset tracker state so IDs start fresh for every video
    pose_model.predictor = None
    warnings = []
    _ffmpeg()   # fail fast if ffmpeg is missing, before processing any frames

    if enhance_mode in ("on", "auto"):
        try:
            enhance.get_zdce()
        except Exception as e:
            warnings.append(f"Enhancement disabled: {e}")
            enhance_mode = "off"

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Cannot open the video. Try an .mp4 file.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    max_frames = int(max_seconds * fps) if max_seconds else None
    total = min(n_total, max_frames) if (n_total and max_frames) else (n_total or max_frames or 0)
    writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))

    cw = 640
    ch = max(int(H * cw / W), 2)
    buf = deque(maxlen=max(int(config.BUFFER_S * fps), 1))
    gate = AlertGate(threshold=score_thr, hold_s=hold_s)
    events, series, seen = [], [], set()
    streaks, prev_wr, speed_ema = {}, {}, {}
    ema_b, enh_on = None, False
    n_alerts, n_enh, frame_i = 0, 0, 0
    t_start = time.time()

    while True:
        ok, frame = cap.read()
        if not ok or (max_frames and frame_i >= max_frames):
            break
        t = frame_i / fps

        # ---- step 1: watch, brighten if dark ----
        gray_mean = float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean())
        ema_b = gray_mean if ema_b is None else 0.9 * ema_b + 0.1 * gray_mean
        if enhance_mode == "on":
            enh_on = True
        elif enhance_mode == "off":
            enh_on = False
        elif ema_b < config.DARK_ON:
            enh_on = True
        elif ema_b > config.DARK_OFF:
            enh_on = False
        frame_in = enhance.enhance_bgr(frame) if enh_on else frame
        n_enh += int(enh_on)

        # ---- step 2: detect objects, people, pose, tracking ----
        ro = obj_model.track(frame_in, persist=True, tracker="bytetrack.yaml", classes=obj_ids,
                             conf=conf, imgsz=imgsz, verbose=False)[0]
        rp = pose_model.track(frame_in, persist=True, tracker="bytetrack.yaml",
                              conf=conf, imgsz=imgsz, verbose=False)[0]

        weapon_boxes = []
        for b in ro.boxes:
            label = ro.names[int(b.cls)]
            tid = int(b.id) if b.id is not None else -1
            if tid != -1 and ("object", tid, label) not in seen:
                seen.add(("object", tid, label))
                events.append(dict(frame=frame_i, time_s=round(t, 2), kind="object", track_id=tid,
                                   label=label, conf=round(float(b.conf), 2), detail=""))
            if label.lower() in config.WEAPON_NAMES:
                weapon_boxes.append(b.xyxy[0].tolist())

        has_kp = rp.keypoints is not None and rp.keypoints.conf is not None
        kxy = rp.keypoints.xy.cpu().numpy() if has_kp else None
        kcf = rp.keypoints.conf.cpu().numpy() if has_kp else None
        people, person_boxes = [], []
        any_hands_up = any_lying = False
        for i, b in enumerate(rp.boxes):
            tid = int(b.id) if b.id is not None else -1
            box = b.xyxy[0].tolist()
            person_boxes.append(box)
            if tid == -1:
                continue
            if ("person", tid) not in seen:
                seen.add(("person", tid))
                events.append(dict(frame=frame_i, time_s=round(t, 2), kind="person", track_id=tid,
                                   label="person", conf=round(float(b.conf), 2), detail=""))

            raw_hands = hands_up(kxy[i], kcf[i]) if has_kp else False
            raw_lying = lying(box)

            # a pose cue must hold for CUE_FRAMES consecutive frames before it counts
            confirmed = {}
            for cue, active in (("hands_up", raw_hands), ("lying", raw_lying)):
                k = (cue, tid)
                streaks[k] = streaks.get(k, 0) + 1 if active else 0
                confirmed[cue] = streaks[k] >= config.CUE_FRAMES
                if confirmed[cue] and k not in seen:
                    seen.add(k)
                    events.append(dict(frame=frame_i, time_s=round(t, 2), kind="cue", track_id=tid,
                                       label=cue, conf=round(float(b.conf), 2), detail=""))
            any_hands_up = any_hands_up or confirmed["hands_up"]
            any_lying = any_lying or confirmed["lying"]

            bh = max(box[3] - box[1], 1.0)
            spd = 0.0
            if has_kp:
                wr = kxy[i][[L_WR, R_WR]]
                wc = kcf[i][[L_WR, R_WR]]
                pv = prev_wr.get(tid)
                if pv is not None and 0 < frame_i - pv[0] <= 3:
                    valid = (wc > 0.4) & (pv[2] > 0.4)
                    if valid.any():
                        d = np.linalg.norm(wr[valid] - pv[1][valid], axis=1).mean()
                        spd = float(d / bh * fps / (frame_i - pv[0]))
                prev_wr[tid] = (frame_i, wr.copy(), wc.copy())
            speed_ema[tid] = 0.5 * speed_ema.get(tid, 0.0) + 0.5 * spd
            people.append(dict(tid=tid, center=((box[0] + box[2]) / 2, (box[1] + box[3]) / 2),
                               h=bh, speed=speed_ema[tid]))

        # ---- step 3 and 4: score, then hold ----
        flags = dict(weapon=bool(weapon_boxes),
                     weapon_near=weapon_near_person(weapon_boxes, person_boxes),
                     fight=fight_like(people, config.FIGHT_SPEED),
                     lying=any_lying, hands_up=any_hands_up)
        score = danger_score(flags)
        reasons = [k for k, v in flags.items() if v]
        ev = gate.update(t, score)
        if ev:
            events.append(dict(frame=frame_i, time_s=round(t, 2), kind="danger", track_id="",
                               label=ev, conf=round(score, 2), detail=", ".join(reasons)))

        # ---- draw ----
        img = ro.plot()
        img = rp.plot(img=img)
        if enh_on:
            iw = max(W // 4, 2)
            ih = max(int(H * iw / W), 2)
            img[10:10 + ih, W - iw - 10:W - 10] = cv2.resize(frame, (iw, ih))
            cv2.putText(img, "original", (W - iw - 6, 10 + ih + 18), FONT, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        draw_hud(img, score, gate.progress(t), hold_s, score_thr, reasons, enh_on)
        buf.append(cv2.resize(img, (cw, ch)))
        writer.write(img)

        # ---- step 5: alert (clip + snapshot + database + Telegram) ----
        if ev == "triggered":
            n_alerts += 1
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clip_path = str(config.ALERTS_DIR / f"alert_{stamp}_{n_alerts}.mp4")
            snap_path = clip_path.replace(".mp4", ".jpg")
            write_clip(list(buf), fps, clip_path)
            cv2.imwrite(snap_path, img)
            alert_id = db.add_alert(camera, t, score, reasons, clip_path, snap_path)
            if send_telegram:
                tg_send(f"ALERT #{alert_id} | {camera} | video time {t:.1f}s | score {score:.2f} | "
                        f"{', '.join(reasons)} | awaiting human review", clip_path)

        series.append(dict(time_s=round(t, 2), score=round(score, 3),
                           brightness=round(gray_mean, 1), enhanced=int(enh_on)))
        frame_i += 1
        if on_progress and frame_i % 5 == 0:
            on_progress(frame_i, total)

    cap.release()
    writer.release()
    speed = frame_i / max(time.time() - t_start, 1e-6)

    # convert to H.264 so it plays in the browser
    web_path = out_path.replace(".mp4", "_web.mp4")
    _to_h264(out_path, web_path)
    os.remove(out_path)
    if on_progress:
        on_progress(frame_i, frame_i)
    return dict(video_path=web_path, events=events, series=series, n_alerts=n_alerts,
                speed=round(speed, 1), enhanced_fraction=round(n_enh / max(frame_i, 1), 3),
                warnings=warnings)
