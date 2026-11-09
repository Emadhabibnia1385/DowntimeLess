import sqlite3
from typing import Dict

from fastapi import APIRouter, Depends

from ...db import get_db
from ...deps import Actor, current_workspace, require
from ..reports import events as changelog

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULTS: Dict[str, float] = {
    "cpu_warn": 90, "steal_warn": 10, "ram_warn": 90, "disk_warn": 85, "disk_crit": 95,
    "retrans_warn": 5, "conntrack_crit": 85, "loss_warn": 10, "loss_crit": 50,
    "ssl_warn_days": 21, "ssl_crit_days": 7,
    "quota_basis": 0,  # 0 = count outgoing bytes only, 1 = outgoing plus incoming (some providers bill both)
    # host checks (agent 0.3): live conntrack limits below these mean they were reset after a reboot
    "ct_max_relay": 65536, "ct_max_exit": 262144, "ct_timeout_max": 43200,
    "inode_warn": 85, "journal_warn_mb": 1024, "ntp_unsynced_min": 10,
    # PasarGuard panel truth: minutes a node may stay not connected, Unavailable log lines per 10 minutes,
    # a node's last hour under this share of its own median while the other nodes keep this share
    "node_down_min": 5, "node_unavailable": 5, "node_drop_pct": 30, "node_others_pct": 70,
    "reseller_warn": 85, "reseller_crit": 95, "reseller_hours": 24,
}

# One on/off switch per kind of alert (1 = on); an alert that is off is neither listed as an issue nor sent to Telegram.
RULES = (
    "offline", "cpu", "ram", "disk", "steal", "retrans", "conntrack", "ping", "ssl", "failed_units", "reboot",
    "rebooted", "ip_changed", "resized", "blacklisted", "relay_egress", "relay_filtered", "load_per_core", "quota", "quota_pair",
    "listener_missing", "unit_stopped", "unit_crashloop", "container_down", "container_restarting", "container_unhealthy",
    "container_revived", "dnat_missing", "ip_forward_off", "conntrack_limits_reset", "conntrack_drops", "oom_kill", "inode_high",
    "journal_big", "time_unsynced", "reboot_pending_pkgs", "node_down", "node_silent", "node_usage_drop", "inbound_without_group",
    "reseller_quota", "panel_version_changed", "panel_errors", "dnat_dead_target", "dnat_unknown_target", "relay_forward_broken",
)
DEFAULTS.update({"on_" + r: 1 for r in RULES})


def thresholds(db: sqlite3.Connection, ws: int) -> Dict[str, float]:
    """The workspace's thresholds and switches; a key it never set keeps the default."""
    out = dict(DEFAULTS)
    for r in db.execute("SELECT key, value FROM settings WHERE workspace_id=?", (ws,)):
        if r["key"] in out:
            out[r["key"]] = float(r["value"])
    return out


@router.get("", response_model=Dict[str, float], operation_id="settings_get")
def get_settings_(_: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    return thresholds(db, ws)


@router.put("", response_model=Dict[str, float], operation_id="settings_put")
def put_settings(body: Dict[str, float], _: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
                 db: sqlite3.Connection = Depends(get_db)):
    before = thresholds(db, ws)
    for k, v in body.items():
        if k in DEFAULTS:
            if k.startswith("on_") or k == "quota_basis":
                v = 1 if v else 0
            db.execute(
                "INSERT INTO settings (workspace_id, key, value) VALUES (?,?,?) "
                "ON CONFLICT(workspace_id, key) DO UPDATE SET value=excluded.value",
                (ws, k, str(v)),
            )
    after = thresholds(db, ws)
    changelog.settings_changed(db, ws, before, after)
    return after
