"""SQLite alert store."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
import config


def _conn():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with closing(_conn()) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created TEXT, camera TEXT, video_time REAL,
            score REAL, reasons TEXT, clip TEXT, snapshot TEXT, status TEXT, reviewed_at TEXT)""")
        c.commit()


def add_alert(camera, video_time, score, reasons, clip, snapshot):
    with closing(_conn()) as c:
        cur = c.execute(
            "INSERT INTO alerts (created, camera, video_time, score, reasons, clip, snapshot, status) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), camera, float(video_time), float(score),
             ", ".join(reasons), clip, snapshot, "pending"))
        c.commit()
        return cur.lastrowid


def _public(row):
    d = dict(row)
    clip, snap = d.pop("clip"), d.pop("snapshot")
    d["clip_url"] = f"/files/alerts/{os.path.basename(clip)}" if clip else None
    d["snapshot_url"] = f"/files/alerts/{os.path.basename(snap)}" if snap else None
    d["reasons"] = [r for r in (d["reasons"] or "").split(", ") if r]
    return d


def list_alerts(status=None):
    sql, args = "SELECT * FROM alerts", ()
    if status:
        sql, args = sql + " WHERE status = ?", (status,)
    with closing(_conn()) as c:
        return [_public(r) for r in c.execute(sql + " ORDER BY id DESC", args).fetchall()]


def get_alert(alert_id):
    with closing(_conn()) as c:
        r = c.execute("SELECT * FROM alerts WHERE id = ?", (int(alert_id),)).fetchone()
    return _public(r) if r else None


def set_status(alert_id, status):
    with closing(_conn()) as c:
        c.execute("UPDATE alerts SET status = ?, reviewed_at = ? WHERE id = ?",
                  (status, datetime.now().isoformat(timespec="seconds"), int(alert_id)))
        c.commit()


def cleanup_old():
    """Keep clips only for a short time: unconfirmed alerts for hours, confirmed ones for days."""
    now, removed = datetime.now(), 0
    with closing(_conn()) as c:
        rows = c.execute("SELECT id, created, clip, snapshot, status FROM alerts").fetchall()
        for r in rows:
            age = now - datetime.fromisoformat(r["created"])
            limit = (timedelta(days=config.DAYS_CONFIRMED) if r["status"] == "confirmed"
                     else timedelta(hours=config.HOURS_UNCONFIRMED))
            if age > limit:
                for p in (r["clip"], r["snapshot"]):
                    if p and os.path.exists(p):
                        os.remove(p)
                c.execute("DELETE FROM alerts WHERE id = ?", (r["id"],))
                removed += 1
        c.commit()
    return removed
