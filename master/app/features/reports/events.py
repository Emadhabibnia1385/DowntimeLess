import json
import sqlite3
import time
from typing import Any, Dict, Iterable, Optional

KINDS = (
    "job_created", "job_done", "agent_updated", "server_added", "server_removed", "server_renamed",
    "acct_toggled", "issue_opened", "issue_closed", "rebooted", "ip_changed", "resized", "settings_changed",
    "member_added", "member_role_changed", "member_removed",
)
KEEP_S = 180 * 86400
MAX_TITLE = 200


def record(db: sqlite3.Connection, ws: int, kind: str, title: str, server_id: Optional[int] = None,
           detail: Optional[Dict[str, Any]] = None, ts: Optional[int] = None) -> None:
    """Append one line to the change log of workspace `ws`. Never put a token, key or password in `detail`."""
    db.execute(
        "INSERT INTO events (workspace_id, ts, server_id, kind, title, detail) VALUES (?,?,?,?,?,?)",
        (ws, ts if ts is not None else int(time.time()), server_id, kind, title[:MAX_TITLE], json.dumps(detail or {}, ensure_ascii=False)),
    )


def prune(db: sqlite3.Connection, now: int) -> None:
    db.execute("DELETE FROM events WHERE ts<?", (now - KEEP_S,))  # ws: retention - by age, every workspace alike


def label(row: sqlite3.Row) -> str:
    return row["alias"] or row["name"]


def job_created(db: sqlite3.Connection, server: sqlite3.Row, job_id: int, kind: str, user_id: Optional[int]) -> None:
    record(db, server["workspace_id"], "job_created", "%s: %s" % (label(server), kind), server["id"],
           {"job_id": job_id, "job_kind": kind, "user_id": user_id})


def job_done(db: sqlite3.Connection, server: sqlite3.Row, job_id: int, status: str) -> None:
    """Call before the job row is updated: only a job still waiting for its result is logged, so a repeated report adds nothing."""
    row = db.execute(
        "SELECT kind FROM jobs WHERE id=? AND server_id=? AND status IN ('queued','sent')", (job_id, server["id"])  # ws: agent_server
    ).fetchone()
    if row:
        record(db, server["workspace_id"], "job_done", "%s: %s" % (row["kind"], status), server["id"],
               {"job_id": job_id, "job_kind": row["kind"], "status": status})


def server_patched(db: sqlite3.Connection, before: sqlite3.Row, changes: Dict[str, Any]) -> None:
    """`changes` are the columns about to be written; only real differences are logged."""
    ws = before["workspace_id"]
    for field in ("name", "alias"):
        if field in changes and changes[field] != before[field]:
            record(db, ws, "server_renamed", "%s: %s -> %s" % (field, before[field], changes[field]), before["id"], {"field": field, "old": before[field], "new": changes[field]})
    if "acct_on" in changes and int(changes["acct_on"]) != int(before["acct_on"]):
        record(db, ws, "acct_toggled", "%s: byte counting %s" % (label(before), "on" if changes["acct_on"] else "off"), before["id"], {"acct_on": bool(changes["acct_on"])})


def settings_changed(db: sqlite3.Connection, ws: int, before: Dict[str, float], after: Dict[str, float]) -> None:
    changed = sorted(k for k in after if before.get(k) != after[k])
    if changed:
        record(db, ws, "settings_changed", "settings: " + ", ".join(changed), None, {"keys": changed, "old": {k: before.get(k) for k in changed}, "new": {k: after[k] for k in changed}})


def report_changes(db: sqlite3.Connection, server: sqlite3.Row, body: Any, now: int, changes: Dict[str, Any]) -> None:
    """From one agent report: a new agent version, and the reboot, IP change or resize that servers.events.detect found."""
    sid, name, ws = server["id"], label(server), server["workspace_id"]
    if server["agent_version"] and body.agent_version and server["agent_version"] != body.agent_version:
        record(db, ws, "agent_updated", "%s: agent %s -> %s" % (name, server["agent_version"], body.agent_version), sid, {"old": server["agent_version"], "new": body.agent_version}, now)
    uptime = (body.model_extra or {}).get("uptime_s")
    if "rebooted_at" in changes:
        record(db, ws, "rebooted", "%s: rebooted (uptime %ss)" % (name, int(uptime) if isinstance(uptime, (int, float)) else "?"), sid, {"uptime_s": uptime}, now)
    if "ip_changed_at" in changes:
        record(db, ws, "ip_changed", "%s: %s -> %s" % (name, changes.get("prev_ip"), body.public_ip), sid, {"old": changes.get("prev_ip"), "new": body.public_ip}, now)
    if "resized_at" in changes:
        try:
            was = json.loads(changes.get("resized_from") or "{}")
        except ValueError:
            was = {}
        record(db, ws, "resized", "%s: smaller machine" % name, sid, {"was": was}, now)


def issue_events(db: sqlite3.Connection, ws: int, kind: str, rows: Iterable[Dict[str, Any]], ts: Optional[int] = None) -> None:
    for r in rows:
        record(db, ws, kind, "%s: %s" % (r.get("server_name") or "-", r.get("code") or r.get("key")), r.get("server_id"),
               {"key": r.get("key"), "code": r.get("code"), "severity": r.get("severity")}, r.get("ts", ts))
