"""Learned fight detector: pose features -> rolling window -> fight probability.

PoseFeat and window_vec MUST stay identical to the training notebook
(aquila_fight_classifier_training.ipynb), otherwise the classifier gets features
it was never trained on and its probabilities become meaningless.
"""
import threading
from collections import deque

import numpy as np

import config
from scoring import L_SH, R_SH, L_WR, R_WR

_lock = threading.Lock()
_state = {"loaded": False, "bundle": None, "error": ""}


def get_fight_bundle():
    """Load the .joblib once. Returns (bundle_or_None, error_text). Never raises."""
    with _lock:
        if not _state["loaded"]:
            _state["loaded"] = True
            try:
                import joblib
                _state["bundle"] = joblib.load(config.FIGHT_MODEL_PATH)
            except Exception as e:
                _state["error"] = (f"Fight classifier not loaded from {config.FIGHT_MODEL_PATH} "
                                   f"({type(e).__name__}: {e}). The old fight rule is used instead.")
        return _state["bundle"], _state["error"]


def _iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return float(inter / ua) if ua > 0 else 0.0


class PoseFeat:
    """One frame of tracked poses -> a small feature vector (same as the training notebook)."""

    def __init__(self):
        self.prev_wr, self.ema = {}, {}

    def update(self, frame_i, fps, boxes, ids, kxy, kcf):
        n = len(boxes)
        spd, hts, ctr = [], [], []
        ext, hup = 0.0, 0
        for i in range(n):
            b, tid = boxes[i], ids[i]
            bh = max(float(b[3] - b[1]), 1.0)
            hts.append(bh)
            ctr.append(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
            s = 0.0
            if tid != -1:
                wr, wc = kxy[i][[L_WR, R_WR]], kcf[i][[L_WR, R_WR]]
                pv = self.prev_wr.get(tid)
                if pv is not None and 0 < frame_i - pv[0] <= 3:
                    valid = (wc > 0.4) & (pv[2] > 0.4)
                    if valid.any():
                        d = np.linalg.norm(wr[valid] - pv[1][valid], axis=1).mean()
                        s = float(d / bh * fps / (frame_i - pv[0]))
                self.prev_wr[tid] = (frame_i, wr.copy(), wc.copy())
                self.ema[tid] = 0.5 * self.ema.get(tid, 0.0) + 0.5 * s
                s = self.ema[tid]
            spd.append(s)
            for sh, w in ((L_SH, L_WR), (R_SH, R_WR)):
                if kcf[i][sh] > 0.4 and kcf[i][w] > 0.4:
                    ext = max(ext, float(np.linalg.norm(kxy[i][w] - kxy[i][sh])) / bh)
                if kcf[i][sh] > 0.5 and kcf[i][w] > 0.5 and kxy[i][w][1] < kxy[i][sh][1]:
                    hup += 1
        close, iou_max = 5.0, 0.0
        for i in range(n):
            for j in range(i + 1, n):
                d = float(np.hypot(ctr[i][0] - ctr[j][0], ctr[i][1] - ctr[j][1]))
                close = min(close, d / max(hts[i], hts[j]))
                iou_max = max(iou_max, _iou(boxes[i], boxes[j]))
        s_sorted = sorted(spd, reverse=True) + [0.0, 0.0]
        return [float(n), s_sorted[0], s_sorted[1], close, ext, float(hup), iou_max]


def window_vec(W):
    """W: (frames, 7 features) -> one vector describing the window."""
    return np.concatenate([W.mean(0), W.max(0), W.std(0), np.percentile(W, 90, axis=0)])


class FightDetector:
    """Feeds pose results into a rolling window and returns a smoothed fight probability.
    Create a NEW instance for every video (it keeps per-track history)."""

    def __init__(self, bundle, fps):
        self.clf, self.stride = bundle["model"], bundle["stride"]
        eff = fps / self.stride
        self.n = max(int(bundle["win_s"] * eff), 4)
        self.hop = max(int(bundle["hop_s"] * eff), 1)
        self.pf, self.buf, self.count, self.p = PoseFeat(), deque(maxlen=self.n), 0, 0.0

    def update(self, frame_i, fps, rp):
        """rp = the ultralytics result of the pose model for this frame."""
        if frame_i % self.stride:
            return self.p
        if rp.boxes is not None and len(rp.boxes) and rp.keypoints is not None:
            boxes = rp.boxes.xyxy.cpu().numpy()
            ids = rp.boxes.id.int().cpu().tolist() if rp.boxes.id is not None else [-1] * len(boxes)
            kxy = rp.keypoints.xy.cpu().numpy()
            kcf = rp.keypoints.conf.cpu().numpy() if rp.keypoints.conf is not None else np.ones(kxy.shape[:2])
        else:
            boxes, ids, kxy, kcf = np.zeros((0, 4)), [], np.zeros((0, 17, 2)), np.zeros((0, 17))
        self.buf.append(self.pf.update(frame_i, fps, boxes, ids, kxy, kcf))
        self.count += 1
        if len(self.buf) == self.n and self.count % self.hop == 0:
            raw = float(self.clf.predict_proba(window_vec(np.array(self.buf, dtype=np.float32))[None, :])[0, 1])
            self.p = config.FIGHT_SMOOTH * raw + (1 - config.FIGHT_SMOOTH) * self.p
        return self.p
