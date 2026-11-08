import sqlite3
import time
from typing import Any, Dict, List, Optional

from ..overview import detectors
from ..settings.router import thresholds
from .common import has_column, name_of


def available(db: sqlite3.Connection) -> bool:
    return has_column(db, "servers", "quota_gb")


def forecast(db: sqlite3.Connection, now: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
    """Servers with a quota, soonest to run out first, from the same forecast the quota alerts use."""
    if not available(db):
        return None
    now = now or int(time.time())
    th = thresholds(db)
    out: List[Dict[str, Any]] = []
    for s in db.execute("SELECT * FROM servers WHERE quota_gb IS NOT NULL AND quota_gb>0"):
        f = detectors.quota_forecast(db, s, th, now)
        if f:
            out.append({"server_id": s["id"], "server_name": name_of(s), **f})
    out.sort(key=lambda r: (r["days_left"] is None, r["days_left"] if r["days_left"] is not None else 0))
    return out
