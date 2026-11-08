import logging
import threading
import time

from . import alerts
from .db import connect
from .features.issues import service as incidents_svc
from .features.links import service as links_svc
from .features.reports import events as changelog
from .features.servers.service import status_of
from .features.settings.router import thresholds
from .features.ssl import service as ssl_svc
from .telegram import Telegram

log = logging.getLogger("dl.monitor")


def sweep(tg: Telegram) -> None:
    """Every workspace on its own: its thresholds, its fleet, its incidents and its people. Then the shared housekeeping."""
    db = connect()
    try:
        ssl_svc.probe_due(db)  # each domain is probed for its own row; nothing crosses workspaces
        ssl_svc.drop_stale_auto(db)
        for ws in [r["id"] for r in db.execute("SELECT id FROM workspaces ORDER BY id").fetchall()]:
            try:
                sweep_workspace(db, tg, ws)
            except Exception:
                log.exception("sweep of workspace %d failed", ws)
        cut = int(time.time())
        db.execute("DELETE FROM metrics WHERE ts<?", (cut - 90 * 86400,))  # ws: retention - by age, every workspace alike
        db.execute("DELETE FROM pings WHERE ts<?", (cut - 7 * 86400,))  # ws: retention - by age, every workspace alike
        links_svc.prune(db, cut)
        changelog.prune(db, cut)
        db.execute("DELETE FROM sessions WHERE expires_at<?", (cut,))
    finally:
        db.close()


def sweep_workspace(db, tg: Telegram, ws: int) -> None:
    """Tell this workspace's admins once when a server goes quiet and once when it comes back, then its incidents."""
    th = thresholds(db, ws)
    for s in db.execute("SELECT * FROM servers WHERE workspace_id=? AND last_seen IS NOT NULL", (ws,)).fetchall():
        st, label = status_of(s), s["alias"] or s["name"]
        if not th["on_offline"]:
            continue
        if st == "offline" and not s["offline_notified"]:
            db.execute("UPDATE servers SET offline_notified=1 WHERE id=? AND workspace_id=?", (s["id"], ws))
            alerts.notify(tg, ws, "offline", "🔴 <b>%s</b> گزارش نمی‌دهد (آخرین گزارش %d ثانیه پیش)." % (label, time.time() - s["last_seen"]))
        elif st == "online" and s["offline_notified"]:
            db.execute("UPDATE servers SET offline_notified=0 WHERE id=? AND workspace_id=?", (s["id"], ws))
            alerts.notify(tg, ws, "offline", "🟢 <b>%s</b> دوباره آنلاین شد." % label)
    if th["on_ssl"]:
        _ssl_alerts(db, tg, ws)
    try:
        events = incidents_svc.record(db, ws, int(time.time()))
    except Exception:
        log.exception("issue history failed")
        events = []
    try:
        alerts.dispatch(db, tg, ws, events, int(time.time()))
    except Exception:
        log.exception("alert dispatch failed")


def _ssl_alerts(db, tg: Telegram, ws: int) -> None:
    """One Telegram message per certificate each time its level changes, none while it stays the same."""
    seen = set()
    for r in ssl_svc.rows(db, ws):
        if r["stale"]:
            continue
        seen.add(r["key"])
        old = db.execute("SELECT level FROM alert_state WHERE workspace_id=? AND key=?", (ws, "ssl:" + r["key"])).fetchone()
        if (old["level"] if old else "ok") == r["level"]:
            continue
        db.execute(
            "INSERT INTO alert_state (workspace_id, key, level) VALUES (?,?,?) "
            "ON CONFLICT(workspace_id, key) DO UPDATE SET level=excluded.level",
            (ws, "ssl:" + r["key"], r["level"]),
        )
        if r["level"] == "ok":
            continue
        why = r["error"] or ("%d روز تا انقضا" % r["days_left"])
        where = r["server_name"] or "بررسی از بیرون"
        alerts.notify(tg, ws, "ssl", "🔐 گواهی <b>%s</b> (%s): %s · تمدید خودکار: %s" % (r["name"], where, why, {"on": "فعال", "off": "غیرفعال", "unknown": "نامشخص"}[r["auto_renew"]]))
    for row in db.execute("SELECT key FROM alert_state WHERE workspace_id=? AND key LIKE 'ssl:%'", (ws,)).fetchall():
        if row["key"][4:] not in seen:
            db.execute("DELETE FROM alert_state WHERE workspace_id=? AND key=?", (ws, row["key"]))


def run_forever(tg: Telegram, stop: threading.Event) -> None:
    while not stop.wait(15):
        try:
            sweep(tg)
        except Exception:
            log.exception("sweep failed")
