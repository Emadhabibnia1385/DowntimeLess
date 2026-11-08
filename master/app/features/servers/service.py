import json
import re
import sqlite3
import time
from typing import Any, Dict, Optional

from ...settings import get_settings

RANGES = {"1h": (3600, 30), "24h": (86400, 300), "7d": (7 * 86400, 1800), "30d": (30 * 86400, 7200)}
# read-only kinds any admin may queue; the rest also need the server permission level
SAFE_KINDS = {"ping", "tcp_check", "speedtest_down", "speedtest_up"}
MUTATING_KINDS = {"apt_upgrade_safe", "reboot", "self_update"}
# the agent replacing its own file from this master changes nothing else on the server
ANY_LEVEL_KINDS = {"self_update"}


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


_agent_cache: Dict[str, Any] = {"mtime": None, "version": None}


def current_agent_version() -> Optional[str]:
    """The version of the agent file this master serves, re-read when the file changes."""
    path = get_settings().agent_dir / "agent.py"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    if _agent_cache["mtime"] != mtime:
        m = re.search(r'^VERSION\s*=\s*"(\d+\.\d+\.\d+)"', path.read_text(encoding="utf-8"), re.M)
        _agent_cache.update(mtime=mtime, version=m.group(1) if m else None)
    return _agent_cache["version"]


def _version_key(v: str) -> tuple:
    return tuple(int(x) for x in v.split("."))


def agent_outdated(version: Optional[str]) -> bool:
    latest = current_agent_version()
    if not version or not latest or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        return False
    return _version_key(version) < _version_key(latest)


def role_columns(role: str) -> Dict[str, Any]:
    """The stored columns for an API role: a panel-only server is 'panel' plus a flag."""
    if role == "panel_only":
        return {"role": "panel", "panel_only": 1}
    return {"role": role, "panel_only": 0}


def role_of(row: sqlite3.Row) -> str:
    return "panel_only" if row["role"] == "panel" and row["panel_only"] else row["role"]


def server_out(row: sqlite3.Row) -> Dict[str, Any]:
    keys = ("id", "name", "alias", "permission", "last_seen", "hostname", "public_ip", "country", "city", "org", "agent_version")
    return {
        **{k: row[k] for k in keys},
        "role": role_of(row),
        "status": status_of(row),
        "agent_outdated": agent_outdated(row["agent_version"]),
        "latest": latest_of(row),
    }


def install_command(token: str) -> str:
    url = get_settings().public_url.rstrip("/")
    return "curl -fsSL %s/agent/install.sh | sudo bash -s -- --master %s --token %s" % (url, url, token)
