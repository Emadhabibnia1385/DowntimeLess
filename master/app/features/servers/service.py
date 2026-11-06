import json
import sqlite3
import time
from typing import Any, Dict, Optional

from ...settings import get_settings

RANGES = {"1h": (3600, 30), "24h": (86400, 300), "7d": (7 * 86400, 1800), "30d": (30 * 86400, 7200)}
# read-only kinds any admin may queue; the rest also need the server permission level
SAFE_KINDS = {"ping", "tcp_check", "speedtest_down", "speedtest_up"}
MUTATING_KINDS = {"apt_upgrade_safe", "reboot", "self_update"}


def status_of(row: sqlite3.Row, now: Optional[float] = None) -> str:
    if not row["last_seen"]:
        return "pending"
    s = get_settings()
    return "online" if (now or time.time()) - row["last_seen"] <= s.interval_s * s.offline_after else "offline"


def latest_of(row: sqlite3.Row) -> Dict[str, Any]:
    rep = json.loads(row["last_report"]) if row["last_report"] else {}
    net = rep.get("net") or {}
    total, avail = rep.get("ram_total_mb"), rep.get("ram_avail_mb")
    dt, du = rep.get("disk_total_gb"), rep.get("disk_used_gb")
    return {
        "cpu_pct": rep.get("cpu_pct"), "steal_pct": rep.get("steal_pct"),
        "ram_pct": round((total - avail) * 100 / total, 1) if total else None,
        "disk_pct": round(du * 100 / dt, 1) if dt else None,
        "rx_bps": net.get("rx_bps"), "tx_bps": net.get("tx_bps"),
        "uptime_s": rep.get("uptime_s"), "load1": rep.get("load1"),
        "tcp_retrans_pct": rep.get("tcp_retrans_pct"), "conntrack_pct": rep.get("conntrack_pct"),
        "reboot_required": bool(rep.get("reboot_required")), "failed_units": rep.get("failed_units") or [],
    }


def server_out(row: sqlite3.Row) -> Dict[str, Any]:
    keys = ("id", "name", "alias", "role", "permission", "last_seen", "hostname", "public_ip", "country", "city", "org", "agent_version")
    return {**{k: row[k] for k in keys}, "status": status_of(row), "latest": latest_of(row)}


def install_command(token: str) -> str:
    url = get_settings().public_url.rstrip("/")
    return "curl -fsSL %s/agent/install.sh | sudo bash -s -- --master %s --token %s" % (url, url, token)
