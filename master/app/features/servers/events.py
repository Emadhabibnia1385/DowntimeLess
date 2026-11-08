"""State changes read off consecutive agent reports: a reboot, a new public IP, a smaller machine."""
import json
import sqlite3
from typing import Any, Dict, Optional

# a RAM total that shrinks by less than this share is rounding, not a resize
RAM_TOLERANCE = 0.03


def detect(server: sqlite3.Row, body: Any, public_ip: Optional[str], now: int) -> Dict[str, Any]:
    """Columns of `servers` to set because this report differs from the previous one; empty when nothing changed."""
    try:
        old = json.loads(server["last_report"]) if server["last_report"] else {}
    except ValueError:
        old = {}
    extra = body.model_extra or {}
    changes: Dict[str, Any] = {}
    up_old, up_new = old.get("uptime_s"), extra.get("uptime_s")
    if isinstance(up_old, (int, float)) and isinstance(up_new, (int, float)) and up_new < up_old:
        changes["rebooted_at"] = now
    # the very first IP is not a change: there must be a known one that now differs
    if server["public_ip"] and public_ip and public_ip != server["public_ip"]:
        changes.update(prev_ip=server["public_ip"], ip_changed_at=now)
    was: Dict[str, Any] = {}
    cores_old, cores_new = old.get("cpu_cores"), body.cpu_cores
    if isinstance(cores_old, (int, float)) and cores_new is not None and cores_new < cores_old:
        was["cpu_cores"] = [cores_old, cores_new]
    ram_old, ram_new = old.get("ram_total_mb"), body.ram_total_mb
    if isinstance(ram_old, (int, float)) and ram_new is not None and ram_new < ram_old * (1 - RAM_TOLERANCE):
        was["ram_total_mb"] = [ram_old, ram_new]
    if was:
        changes.update(resized_at=now, resized_from=json.dumps(was))
    return changes
