"""Danger-score rules and the alert gate (from the notebook, unchanged in behaviour)."""
import numpy as np
import config

L_SH, R_SH, L_WR, R_WR = 5, 6, 9, 10   # COCO keypoint indices


def hands_up(kp_xy, kp_conf):
    """A wrist above the same-side shoulder (image y grows downward)."""
    for sh, wr in ((L_SH, L_WR), (R_SH, R_WR)):
        if kp_conf[sh] > 0.5 and kp_conf[wr] > 0.5 and kp_xy[wr][1] < kp_xy[sh][1]:
            return True
    return False


def lying(box):
    """Person box much wider than tall."""
    w, h = box[2] - box[0], box[3] - box[1]
    return w > 1.3 * h


def weapon_near_person(weapon_boxes, person_boxes, margin=0.2):
    for wb in weapon_boxes:
        cx, cy = (wb[0] + wb[2]) / 2, (wb[1] + wb[3]) / 2
        for pb in person_boxes:
            mx, my = (pb[2] - pb[0]) * margin, (pb[3] - pb[1]) * margin
            if pb[0] - mx <= cx <= pb[2] + mx and pb[1] - my <= cy <= pb[3] + my:
                return True
    return False


def fight_like(people, thr):
    """Two people close together with fast arm movement. A weak heuristic, not a violence classifier."""
    for i in range(len(people)):
        for j in range(i + 1, len(people)):
            a, b = people[i], people[j]
            dist = float(np.hypot(a["center"][0] - b["center"][0], a["center"][1] - b["center"][1]))
            close = dist < 1.3 * max(a["h"], b["h"])
            fast, slow = max(a["speed"], b["speed"]), min(a["speed"], b["speed"])
            if close and fast >= thr and slow >= 0.4 * thr:
                return True
    return False


def danger_score(flags, w=config.WEIGHTS):
    s = 0.0
    if flags.get("weapon_near"):
        s += w["weapon_near"]
    elif flags.get("weapon"):
        s += w["weapon"]
    if flags.get("fight"):    s += w["fight"]
    if flags.get("lying"):    s += w["lying"]
    if flags.get("hands_up"): s += w["hands_up"]
    return min(1.0, s)


class AlertGate:
    """Raises an alert only if the score stays high for hold_s seconds.
    A short dip (grace_s) is forgiven; a longer dip cancels. After an alert, wait cooldown_s."""

    def __init__(self, threshold=0.6, hold_s=4.0, grace_s=1.0, cooldown_s=30.0):
        self.threshold, self.hold_s, self.grace_s, self.cooldown_s = threshold, hold_s, grace_s, cooldown_s
        self.start_t = None
        self.last_above_t = None
        self.last_trigger_t = -1e9

    def update(self, t, score):
        ev = None
        if score >= self.threshold:
            self.last_above_t = t
            if self.start_t is None:
                self.start_t = t
                ev = "started"
            if (t - self.start_t) >= self.hold_s and (t - self.last_trigger_t) >= self.cooldown_s:
                self.last_trigger_t = t
                ev = "triggered"
        elif self.start_t is not None and (t - self.last_above_t) > self.grace_s:
            self.start_t = None
            ev = "cancelled"
        return ev

    def progress(self, t):
        if self.start_t is None:
            return 0.0
        return min(1.0, (t - self.start_t) / self.hold_s)
