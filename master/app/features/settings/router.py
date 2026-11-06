import sqlite3
from typing import Dict

from fastapi import APIRouter, Depends

from ...db import get_db
from ...deps import Actor, require

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULTS: Dict[str, float] = {
    "cpu_warn": 90, "steal_warn": 10, "ram_warn": 90, "disk_warn": 85, "disk_crit": 95,
    "retrans_warn": 5, "conntrack_crit": 85, "loss_warn": 10, "loss_crit": 50,
    "ssl_warn_days": 21, "ssl_crit_days": 7,
}


def thresholds(db: sqlite3.Connection) -> Dict[str, float]:
    out = dict(DEFAULTS)
    for r in db.execute("SELECT key, value FROM settings"):
        if r["key"] in out:
            out[r["key"]] = float(r["value"])
    return out


@router.get("", response_model=Dict[str, float], operation_id="settings_get")
def get_settings_(_: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)):
    return thresholds(db)


@router.put("", response_model=Dict[str, float], operation_id="settings_put")
def put_settings(body: Dict[str, float], _: Actor = Depends(require("admin")), db: sqlite3.Connection = Depends(get_db)):
    for k, v in body.items():
        if k in DEFAULTS:
            db.execute("INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
    return thresholds(db)
