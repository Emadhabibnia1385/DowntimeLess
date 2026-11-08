import logging
import threading
import time

from .bot import notify_admins
from .db import connect
from .features.issues import service as incidents_svc
from .features.servers.service import status_of
from .features.settings.router import thresholds
from .features.ssl import service as ssl_svc
from .telegram import Telegram

log = logging.getLogger("dl.monitor")


def sweep(tg: Telegram) -> None:
    """Tell admins once when a server goes quiet and once when it comes back."""
    db = connect()
    try:
        th = thresholds(db)
        for s in db.execute("SELECT * FROM servers WHERE last_seen IS NOT NULL").fetchall():
            st, label = status_of(s), s["alias"] or s["name"]
            if not th["on_offline"]:
                continue
            if st == "offline" and not s["offline_notified"]:
                db.execute("UPDATE servers SET offline_notified=1 WHERE id=?", (s["id"],))
                notify_admins(tg, "🔴 <b>%s</b> گزارش نمی‌دهد (آخرین گزارش %d ثانیه پیش)." % (label, time.time() - s["last_seen"]))
            elif st == "online" and s["offline_notified"]:
                db.execute("UPDATE servers SET offline_notified=0 WHERE id=?", (s["id"],))
                notify_admins(tg, "🟢 <b>%s</b> دوباره آنلاین شد." % label)
        ssl_svc.probe_due(db)
        ssl_svc.drop_stale_auto(db)
        if th["on_ssl"]:
            _ssl_alerts(db, tg)
        try:
            incidents_svc.record(db, int(time.time()))
        except Exception:
            log.exception("issue history failed")
        cut = int(time.time())
        db.execute("DELETE FROM metrics WHERE ts<?", (cut - 90 * 86400,))
        db.execute("DELETE FROM pings WHERE ts<?", (cut - 7 * 86400,))
        db.execute("DELETE FROM sessions WHERE expires_at<?", (cut,))
    finally:
        db.close()


def _ssl_alerts(db, tg: Telegram) -> None:
    """One Telegram message per certificate each time its level changes, none while it stays the same."""
    seen = set()
    for r in ssl_svc.rows(db):
        if r["stale"]:
            continue
        seen.add(r["key"])
        old = db.execute("SELECT level FROM alert_state WHERE key=?", ("ssl:" + r["key"],)).fetchone()
        if (old["level"] if old else "ok") == r["level"]:
            continue
        db.execute("INSERT INTO alert_state (key, level) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET level=excluded.level", ("ssl:" + r["key"], r["level"]))
        if r["level"] == "ok":
            continue
        why = r["error"] or ("%d روز تا انقضا" % r["days_left"])
        where = r["server_name"] or "بررسی از بیرون"
        notify_admins(tg, "🔐 گواهی <b>%s</b> (%s): %s · تمدید خودکار: %s" % (r["name"], where, why, {"on": "فعال", "off": "غیرفعال", "unknown": "نامشخص"}[r["auto_renew"]]))
    for row in db.execute("SELECT key FROM alert_state WHERE key LIKE 'ssl:%'").fetchall():
        if row["key"][4:] not in seen:
            db.execute("DELETE FROM alert_state WHERE key=?", (row["key"],))


def run_forever(tg: Telegram, stop: threading.Event) -> None:
    while not stop.wait(15):
        try:
            sweep(tg)
        except Exception:
            log.exception("sweep failed")
