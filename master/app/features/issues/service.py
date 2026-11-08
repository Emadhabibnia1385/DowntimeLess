import json
import sqlite3
from typing import Any, Dict, List, Optional

from ..overview import service as overview
from ..reports import events as changelog

RANGES = {"24h": 86400, "7d": 7 * 86400, "30d": 30 * 86400}
RANK = {"info": 0, "warning": 1, "critical": 2}
# An issue that blinks off for one sweep (15 s) is the same incident; it closes once it has been absent this long.
GRACE_S = 30
KEEP_S = 90 * 86400
MAX_INCIDENTS = 300
FLAPPING_AT = 3


def record(db: sqlite3.Connection, now: int, found: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Diff the current issues against the open incidents: open, refresh or close, then prune old rows.

    Returns what happened as events ({"type": "open"|"close", ...}) so the caller can tell people."""
    events: List[Dict[str, Any]] = []
    found = overview.issues(db) if found is None else found
    present = {i["id"]: i for i in found}
    open_rows = db.execute("SELECT * FROM incidents WHERE closed_at IS NULL").fetchall()
    open_keys = set()
    for row in open_rows:
        issue = present.get(row["key"])
        if issue is None:
            continue
        open_keys.add(row["key"])
        worst = issue["severity"] if RANK.get(issue["severity"], 0) > RANK.get(row["severity"], 0) else row["severity"]
        db.execute(
            "UPDATE incidents SET last_seen=?, severity=?, title=?, evidence=?, code=?, server_name=? WHERE id=?",
            (now, worst, issue["title"], json.dumps(issue["evidence"], ensure_ascii=False), issue["code"], issue["server_name"], row["id"]),
        )
    for key, issue in present.items():
        if key not in open_keys:
            cur = db.execute(
                "INSERT INTO incidents (key, code, server_id, server_name, severity, title, evidence, opened_at, last_seen) VALUES (?,?,?,?,?,?,?,?,?)",
                (key, issue["code"], issue["server_id"], issue["server_name"], issue["severity"], issue["title"],
                 json.dumps(issue["evidence"], ensure_ascii=False), now, now),
            )
            changelog.record(db, "issue_opened", "%s: %s" % (issue["server_name"] or "-", issue["code"]), issue["server_id"],
                             {"key": key, "code": issue["code"], "severity": issue["severity"]}, now)
            role = db.execute("SELECT role FROM servers WHERE id=?", (issue["server_id"],)).fetchone() if issue["server_id"] else None
            events.append({
                "type": "open", "incident_id": cur.lastrowid, "key": key, "code": issue["code"], "server_id": issue["server_id"],
                "server_name": issue["server_name"], "severity": issue["severity"], "title": issue["title"],
                "suggestion": issue.get("suggestion", ""), "evidence": issue["evidence"], "role": role["role"] if role else None,
            })
    # the end of an incident is the last sweep that still saw it, not the sweep that noticed it was gone
    for row in db.execute(
        "SELECT * FROM incidents WHERE closed_at IS NULL AND last_seen<=? AND (server_id IS NULL OR server_id IN (SELECT id FROM servers))",
        (now - GRACE_S,),
    ).fetchall():
        changelog.record(db, "issue_closed", "%s: %s" % (row["server_name"] or "-", row["code"]), row["server_id"],
                         {"key": row["key"], "code": row["code"], "severity": row["severity"], "duration_s": max(0, row["last_seen"] - row["opened_at"])}, row["last_seen"])
        events.append({
            "type": "close", "incident_id": row["id"], "key": row["key"], "code": row["code"], "server_id": row["server_id"],
            "server_name": row["server_name"], "severity": row["severity"], "title": row["title"], "evidence": _evidence(row["evidence"]),
            "notified_at": row["notified_at"], "duration_s": max(0, row["last_seen"] - row["opened_at"]),
        })
    db.execute("UPDATE incidents SET closed_at=last_seen WHERE closed_at IS NULL AND last_seen<=?", (now - GRACE_S,))
    db.execute(
        "UPDATE incidents SET closed_at=last_seen WHERE closed_at IS NULL AND server_id IS NOT NULL "
        "AND server_id NOT IN (SELECT id FROM servers)"
    )
    db.execute("DELETE FROM incidents WHERE closed_at IS NOT NULL AND closed_at<?", (now - KEEP_S,))
    return events


def recent_counts(db: sqlite3.Connection, now: int, span: int = 86400) -> Dict[str, int]:
    """How many incidents of each issue overlap the last `span` seconds, in one grouped query."""
    rows = db.execute(
        "SELECT key, COUNT(*) AS n FROM incidents WHERE opened_at<=? AND (closed_at IS NULL OR closed_at>=?) GROUP BY key",
        (now, now - span),
    ).fetchall()
    return {r["key"]: r["n"] for r in rows}


def _evidence(raw: Optional[str]) -> Dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def history(db: sqlite3.Connection, range_: str, now: int) -> Dict[str, Any]:
    since = now - RANGES[range_]
    rows = db.execute(
        "SELECT * FROM incidents WHERE opened_at<=? AND (closed_at IS NULL OR closed_at>=?) ORDER BY opened_at DESC, id DESC",
        (now, since),
    ).fetchall()
    by_key: Dict[str, Dict[str, Any]] = {}
    for r in rows:  # newest first, so the first row of a key carries its latest title and evidence
        end = r["closed_at"] if r["closed_at"] is not None else now
        active = _clip(r["opened_at"], end, since, now)
        item = by_key.get(r["key"])
        if item is None:
            item = by_key[r["key"]] = {
                "key": r["key"], "code": r["code"], "server_id": r["server_id"], "server_name": r["server_name"],
                "title": r["title"], "severity": r["severity"], "occurrences": 0, "total_s": 0, "last_at": 0,
                "active_now": False, "flapping": False, "evidence": _evidence(r["evidence"]),
            }
        if RANK.get(r["severity"], 0) > RANK.get(item["severity"], 0):
            item["severity"] = r["severity"]
        item["occurrences"] += 1
        item["total_s"] += active
        item["last_at"] = max(item["last_at"], r["last_seen"] if r["closed_at"] is None else r["closed_at"])
        item["active_now"] = item["active_now"] or r["closed_at"] is None
    summary = sorted(by_key.values(), key=lambda s: (-s["occurrences"], -RANK.get(s["severity"], 0), s["server_name"] or "", s["key"]))
    for s in summary:
        s["flapping"] = s["occurrences"] >= FLAPPING_AT
    incidents = [
        {
            "id": r["id"], "key": r["key"], "code": r["code"], "server_id": r["server_id"], "server_name": r["server_name"],
            "severity": r["severity"], "title": r["title"], "opened_at": r["opened_at"], "closed_at": r["closed_at"],
            "duration_s": max(0, (r["closed_at"] if r["closed_at"] is not None else now) - r["opened_at"]),
        }
        for r in rows[:MAX_INCIDENTS]
    ]
    return {
        "range": range_, "since": since, "summary": summary, "incidents": incidents,
        "totals": {
            "occurrences": sum(s["occurrences"] for s in summary), "issues": len(summary),
            "active_now": sum(1 for s in summary if s["active_now"]),
            "critical": sum(1 for s in summary if s["severity"] == "critical"),
        },
    }


def _clip(start: int, end: int, lo: int, hi: int) -> int:
    return max(0, min(end, hi) - max(start, lo))
