"""Acknowledged issues: the team knows, so the issue stays listed but goes quiet until the ack ends.

Quiet means: not counted with the open issues, no Telegram message (open, flapping or recovery), out of the briefing's
'check first' and the health penalties. It ends by itself when the incident closes (until_resolved), when its time is up
(24h, 7d), or when the issue gets worse than it was when it was acknowledged; 'always' lasts until someone removes it."""
import sqlite3
import time
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from ..reports import events as changelog

MODES: Dict[str, Optional[int]] = {"until_resolved": None, "24h": 86400, "7d": 7 * 86400, "always": None}
RANK = {"info": 0, "warning": 1, "critical": 2}
MAX_NOTE = 200
# the health signals an acknowledged issue code stops counting against its server
HEALTH_KEYS: Dict[str, Tuple[str, ...]] = {
    "cpu": ("cpu_steal",), "steal": ("cpu_steal",), "load_per_core": ("cpu_steal",), "ram": ("memory",), "disk": ("disk",),
    "failed_units": ("units",), "retrans": ("retrans",), "conntrack": ("conntrack", "conntrack_full"), "offline": ("agent_offline",),
    "quota": ("quota", "quota_exhausted"), "ping": ("relay_reachability", "unreachable_from_all_relays"),
    "blacklisted": ("relay_reachability", "unreachable_from_all_relays"), "relay_filtered": ("peer_paths", "all_exits_lossy"),
    "relay_egress": ("peer_paths", "all_exits_lossy"),
}


def rows(db: sqlite3.Connection, ws: int) -> Dict[str, sqlite3.Row]:
    """Every ack of the workspace, expired or not, by issue key, with the name of who made it."""
    return {r["key"]: r for r in db.execute(
        "SELECT a.*, COALESCE(NULLIF(u.name,''), u.tg_username, '') AS by_name FROM issue_acks a "
        "LEFT JOIN users u ON u.id=a.created_by WHERE a.workspace_id=?",
        (ws,),
    ).fetchall()}


def holds(ack: Any, issue: Optional[Dict[str, Any]], now: int) -> bool:
    """An ack keeps an issue quiet while its time is not up and the issue is no worse than when it was acknowledged."""
    if ack["until"] is not None and ack["until"] <= now:
        return False
    return issue is None or RANK.get(issue["severity"], 0) <= RANK.get(ack["severity"], 0)


def annotate(db: sqlite3.Connection, ws: int, issues: List[Dict[str, Any]], now: Optional[int] = None) -> List[Dict[str, Any]]:
    """Mark each issue acked or not (additive fields), in place; an escalated or expired ack is loud at once."""
    now = now or int(time.time())
    acks = rows(db, ws)
    for i in issues:
        ack = acks.get(i["id"])
        on = ack is not None and holds(ack, i, now)
        i["acked"] = on
        i["acked_by"] = (ack["by_name"] or None) if on else None
        i["acked_until"] = ack["until"] if on else None
        i["ack_mode"] = ack["mode"] if on else None
        i["ack_note"] = (ack["note"] or None) if on else None
        i["acked_at"] = ack["created_at"] if on else None
    return issues


def loud(issues: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [i for i in issues if not i.get("acked")]


def acked(issues: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [i for i in issues if i.get("acked")]


def quiet_keys(db: sqlite3.Connection, ws: int, found: Iterable[Dict[str, Any]], now: int) -> Set[str]:
    """Keys whose ack still holds, including issues that just went away (their recovery stays quiet too)."""
    present = {i["id"]: i for i in found}
    return {key for key, ack in rows(db, ws).items() if holds(ack, present.get(key), now)}


def add(db: sqlite3.Connection, ws: int, issue: Dict[str, Any], mode: str, note: str, user_id: Optional[int], now: int) -> Dict[str, Any]:
    """Acknowledge one current issue, or change the ack it already has; logged in the change log."""
    span = MODES[mode]
    until = now + span if span else None
    note = (note or "").strip()[:MAX_NOTE]
    db.execute(
        "INSERT INTO issue_acks (workspace_id, key, mode, until, severity, note, created_by, created_at) VALUES (?,?,?,?,?,?,?,?) "
        "ON CONFLICT(workspace_id, key) DO UPDATE SET mode=excluded.mode, until=excluded.until, severity=excluded.severity, "
        "note=excluded.note, created_by=excluded.created_by, created_at=excluded.created_at",
        (ws, issue["id"], mode, until, issue["severity"], note, user_id, now),
    )
    changelog.record(db, ws, "issue_acked", "%s: %s (%s)" % (issue["server_name"] or "-", issue["code"], mode), issue["server_id"],
                     {"key": issue["id"], "code": issue["code"], "severity": issue["severity"], "mode": mode, "until": until,
                      "user_id": user_id}, now)
    return {"key": issue["id"], "mode": mode, "until": until, "note": note or None, "severity": issue["severity"], "created_at": now}


def remove(db: sqlite3.Connection, ws: int, key: str, user_id: Optional[int], now: int, reason: str = "undo") -> bool:
    """Drop the ack of `key` in this workspace only; False when there was none."""
    row = db.execute("SELECT * FROM issue_acks WHERE workspace_id=? AND key=?", (ws, key)).fetchone()
    if row is None:
        return False
    db.execute("DELETE FROM issue_acks WHERE workspace_id=? AND key=?", (ws, key))
    sid = db.execute("SELECT server_id FROM incidents WHERE workspace_id=? AND key=? ORDER BY id DESC LIMIT 1", (ws, key)).fetchone()
    changelog.record(db, ws, "issue_unacked", "%s (%s)" % (key, reason), sid["server_id"] if sid else None,
                     {"key": key, "mode": row["mode"], "reason": reason, "user_id": user_id}, now)
    return True


def screen(db: sqlite3.Connection, ws: int, found: List[Dict[str, Any]], events: List[Dict[str, Any]], now: int) -> List[Dict[str, Any]]:
    """The monitor's step between the incident log and Telegram.

    Ends the acks whose time is up or whose issue got worse (and tells people about those issues now), drops the open,
    close and flapping events of the issues that stay acknowledged, and forgets until_resolved acks whose incident closed."""
    present = {i["id"]: i for i in found}
    quiet: Set[str] = set()
    woke: List[Dict[str, Any]] = []
    for key, ack in rows(db, ws).items():
        issue = present.get(key)
        if holds(ack, issue, now):
            quiet.add(key)
            continue
        expired = ack["until"] is not None and ack["until"] <= now
        remove(db, ws, key, None, now, "expired" if expired else "escalated")
        if issue is not None:
            woke.append(issue)
    kept = [e for e in events if e["key"] not in quiet]
    opening = {e["key"] for e in kept if e["type"] == "open"}
    for issue in woke:
        if issue["id"] in opening:
            continue
        inc = db.execute(
            "SELECT id FROM incidents WHERE workspace_id=? AND key=? AND closed_at IS NULL ORDER BY id DESC LIMIT 1", (ws, issue["id"])
        ).fetchone()
        if inc is None:
            continue
        role = db.execute(
            "SELECT role FROM servers WHERE id=? AND workspace_id=?", (issue["server_id"], ws)
        ).fetchone() if issue["server_id"] else None
        kept.append({
            "type": "open", "incident_id": inc["id"], "key": issue["id"], "code": issue["code"], "server_id": issue["server_id"],
            "server_name": issue["server_name"], "severity": issue["severity"], "title": issue["title"],
            "suggestion": issue.get("suggestion", ""), "evidence": issue["evidence"], "role": role["role"] if role else None,
        })
    for r in db.execute(
        "SELECT key FROM issue_acks WHERE workspace_id=? AND mode='until_resolved' "
        "AND key NOT IN (SELECT key FROM incidents WHERE workspace_id=? AND closed_at IS NULL)",
        (ws, ws),
    ).fetchall():
        if r["key"] not in present:
            remove(db, ws, r["key"], None, now, "resolved")
    return kept


def health_quiet(issues: Iterable[Dict[str, Any]]) -> Set[str]:
    """The health penalties and gates of one server that only acknowledged issues stand behind."""
    quiet: Set[str] = set()
    loud_keys: Set[str] = set()
    for i in issues:
        keys = HEALTH_KEYS.get(i["code"].split(":")[0], ())
        (quiet if i.get("acked") else loud_keys).update(keys)
    return quiet - loud_keys


def screen_health(status: str, score: Optional[int], gates: List[Dict[str, Any]], pens: List[Dict[str, Any]],
                  quiet: Set[str]) -> Tuple[Optional[int], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Health without what the team acknowledged; an acknowledged offline server has no score rather than zero."""
    if not quiet:
        return score, gates, pens
    gates = [g for g in gates if g["key"] not in quiet]
    pens = [p for p in pens if p["key"] not in quiet]
    if status == "offline":
        return (None if not gates else score), gates, pens
    if score is not None:
        score = max(0, 100 - sum(p["points"] for p in pens))
    return score, gates, pens


def brief(issues: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The acknowledged issues as the briefing lists them, so an assistant still knows they are there."""
    return [{
        "severity": i["severity"], "server_id": i["server_id"], "server": i["server_name"], "code": i["code"], "title": i["title"],
        "mode": i["ack_mode"], "until": i["acked_until"], "by": i["acked_by"], "note": i["ack_note"],
    } for i in issues if i.get("acked")]
