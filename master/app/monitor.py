import logging
import threading
import time

from .bot import notify_admins
from .db import connect
from .features.servers.service import status_of
from .telegram import Telegram

log = logging.getLogger("dl.monitor")


def sweep(tg: Telegram) -> None:
    """Tell admins once when a server goes quiet and once when it comes back."""
    db = connect()
    try:
        for s in db.execute("SELECT * FROM servers WHERE last_seen IS NOT NULL"):
            st, label = status_of(s), s["alias"] or s["name"]
            if st == "offline" and not s["offline_notified"]:
                db.execute("UPDATE servers SET offline_notified=1 WHERE id=?", (s["id"],))
                notify_admins(tg, "🔴 <b>%s</b> گزارش نمی‌دهد (آخرین گزارش %d ثانیه پیش)." % (label, time.time() - s["last_seen"]))
            elif st == "online" and s["offline_notified"]:
                db.execute("UPDATE servers SET offline_notified=0 WHERE id=?", (s["id"],))
                notify_admins(tg, "🟢 <b>%s</b> دوباره آنلاین شد." % label)
        cut = int(time.time())
        db.execute("DELETE FROM metrics WHERE ts<?", (cut - 90 * 86400,))
        db.execute("DELETE FROM pings WHERE ts<?", (cut - 7 * 86400,))
        db.execute("DELETE FROM sessions WHERE expires_at<?", (cut,))
    finally:
        db.close()


def run_forever(tg: Telegram, stop: threading.Event) -> None:
    while not stop.wait(15):
        try:
            sweep(tg)
        except Exception:
            log.exception("sweep failed")
