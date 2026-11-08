"""Where each alert goes (panel only, the admins, or a Telegram channel) and the messages for incidents."""
import json
import logging
import sqlite3
import time
from html import escape
from typing import Any, Dict, List, Optional

from .bot import notify_admins
from .db import connect
from .features.settings.router import RULES, thresholds
from .telegram import Telegram

log = logging.getLogger("dl.alerts")

ADMINS = "admins"
PANEL = "panel"
# routes of alerts that were already sent to the admins before routes existed, plus the urgent new ones
_ADMIN_RULES = ("offline", "ssl", "conntrack", "ping", "disk", "rebooted", "ip_changed", "blacklisted", "quota",
                "listener_missing", "unit_stopped", "container_down", "dnat_missing", "ip_forward_off", "conntrack_drops",
                "node_down", "node_silent")
DEFAULT_ROUTES: Dict[str, str] = {rule: (ADMINS if rule in _ADMIN_RULES else PANEL) for rule in RULES}
# sent by their own flow, not from the incident log
OWN_FLOW = ("offline", "ssl")
# an event that only matters for some roles
ONLY_ROLES = {"rebooted": ("relay", "exit")}
EMOJI = {"critical": "🔴", "warning": "🟠", "info": "🔵"}
FLAP_AT, FLAP_WINDOW_S = 3, 3600
_REBOOT_CODES = {"reboot_required": "reboot"}


def rule_of(code: Optional[str]) -> Optional[str]:
    """The alert rule an issue code belongs to; None for issues that only live in the panel."""
    base = (code or "").split(":")[0]
    base = _REBOOT_CODES.get(base, base)
    if base.startswith("ssl"):
        return "ssl"
    return base if base in RULES else None


def valid_route(db: sqlite3.Connection, ws: int, route: str) -> bool:
    """Panel, admins, or a channel of this workspace; another workspace's channel is not a route here."""
    if route in (PANEL, ADMINS):
        return True
    if route.startswith("channel:") and route[8:].isdigit():
        return db.execute(
            "SELECT 1 FROM telegram_channels WHERE id=? AND workspace_id=? AND verified_at IS NOT NULL", (int(route[8:]), ws)
        ).fetchone() is not None
    return False


def routes(db: sqlite3.Connection, ws: int) -> Dict[str, str]:
    """The route of every rule: what the owner chose, else the default; a route to a deleted channel falls back."""
    out = dict(DEFAULT_ROUTES)
    for r in db.execute("SELECT rule, route FROM rule_routes WHERE workspace_id=?", (ws,)):
        if r["rule"] in out and valid_route(db, ws, r["route"]):
            out[r["rule"]] = r["route"]
    return out


def notify(tg: Telegram, ws: int, rule: str, text: str, thread: Optional[int] = None) -> None:
    """Send `text` where `rule` is routed in workspace `ws`. Never raises: a failed send must not stop the monitor."""
    try:
        db = connect()
        try:
            route = routes(db, ws).get(rule, PANEL)
            channel = None
            if route.startswith("channel:"):
                channel = db.execute(
                    "SELECT chat_id FROM telegram_channels WHERE id=? AND workspace_id=? AND verified_at IS NOT NULL", (int(route[8:]), ws)
                ).fetchone()
        finally:
            db.close()
        if route == PANEL or (route.startswith("channel:") and not channel):
            return
        if route == ADMINS:
            notify_admins(tg, ws, text)
        else:
            chat = int(channel["chat_id"]) if channel["chat_id"].lstrip("-").isdigit() else channel["chat_id"]
            if thread is None:
                tg.send(chat, text)
            else:
                tg.send(chat, text, thread=thread)
    except Exception:
        log.exception("notify %s failed", rule)


# ---- messages ----------------------------------------------------------------------------------

def _evidence_line(evidence: Dict[str, Any]) -> str:
    parts = []
    for key, value in list(evidence.items())[:6]:
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            value = ",".join(str(v) for v in value[:5])
        elif isinstance(value, dict):
            value = ",".join("%s=%s" % (k, v) for k, v in value.items())
        parts.append("%s=%s" % (key, value))
    return " · ".join(parts)[:300]


def open_message(event: Dict[str, Any]) -> str:
    lines = ["%s <b>%s</b>: %s" % (EMOJI.get(event["severity"], "🔵"), escape(event["server_name"] or ""), escape(event["title"] or ""))]
    if event.get("suggestion"):
        lines.append(escape(event["suggestion"]))
    line = _evidence_line(event.get("evidence") or {})
    if line:
        lines.append("<code>%s</code>" % escape(line))
    return "\n".join(lines)


def close_message(event: Dict[str, Any]) -> str:
    minutes = max(1, int(event["duration_s"] / 60))
    return "🟢 <b>%s</b>: %s برطرف شد (پس از %d دقیقه)." % (escape(event["server_name"] or ""), escape(event["title"] or ""), minutes)


def flapping_message(event: Dict[str, Any], count: int) -> str:
    return "🟡 <b>%s</b>: %s ناپایدار است (%d بار در یک ساعت باز و بسته شد)؛ تا یک ساعت پایداری پیام دیگری نمی‌آید." % (
        escape(event["server_name"] or ""), escape(event["title"] or ""), count)


# ---- incident events -----------------------------------------------------------------------------

def dispatch(db: sqlite3.Connection, tg: Telegram, ws: int, events: List[Dict[str, Any]], now: int) -> None:
    """One message when an incident opens and one when it closes, with flapping squashed into a single note."""
    th = thresholds(db, ws)
    chosen = routes(db, ws)
    for ev in events:
        rule = rule_of(ev["code"])
        if rule is None or rule in OWN_FLOW or not th.get("on_" + rule, 1):
            continue
        if rule in ONLY_ROLES and ev.get("role") not in ONLY_ROLES[rule]:
            continue
        if chosen[rule] == PANEL:
            continue
        if ev["type"] == "open":
            _open(db, tg, ws, ev, rule, now)
        elif ev["type"] == "close" and ev.get("notified_at"):
            notify(tg, ws, rule, close_message(ev))
    _forget_stable(db, ws, now)


def _open(db: sqlite3.Connection, tg: Telegram, ws: int, ev: Dict[str, Any], rule: str, now: int) -> None:
    if db.execute("SELECT 1 FROM flapping WHERE workspace_id=? AND key=?", (ws, ev["key"])).fetchone():
        return
    opened = db.execute(
        "SELECT COUNT(*) FROM incidents WHERE workspace_id=? AND key=? AND opened_at>=?", (ws, ev["key"], now - FLAP_WINDOW_S)
    ).fetchone()[0]
    if opened >= FLAP_AT:
        db.execute(
            "INSERT INTO flapping (workspace_id, key, since) VALUES (?,?,?) ON CONFLICT(workspace_id, key) DO UPDATE SET since=excluded.since",
            (ws, ev["key"], now),
        )
        notify(tg, ws, rule, flapping_message(ev, opened))
        return
    db.execute("UPDATE incidents SET notified_at=? WHERE id=? AND workspace_id=?", (now, ev["incident_id"], ws))
    notify(tg, ws, rule, open_message(ev))


def _forget_stable(db: sqlite3.Connection, ws: int, now: int) -> None:
    """A flapping key is quiet again once it has not opened a new incident for an hour."""
    for row in db.execute("SELECT key FROM flapping WHERE workspace_id=?", (ws,)).fetchall():
        if not db.execute(
            "SELECT 1 FROM incidents WHERE workspace_id=? AND key=? AND opened_at>=?", (ws, row["key"], now - FLAP_WINDOW_S)
        ).fetchone():
            db.execute("DELETE FROM flapping WHERE workspace_id=? AND key=?", (ws, row["key"]))
