"""Invites by Telegram username: a pending membership that the person with that username claims by starting the bot
or by linking Telegram to their account.

A Telegram username can change hands, so an invite is a weaker proof than a numeric id: it grants at most `operator`,
lives 14 days and is claimed once. Whoever has the username only ASKS (says yes in the bot, or links Telegram); the
inviting workspace's owner approves in the panel, seeing the numeric Telegram id and name, so a squatter on a username
is stopped before any access. A claim never changes an existing membership (no promotion, no demotion)."""
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional

from .errors import DLError
from .features.reports import events as changelog

INVITE_TTL = 14 * 86400
INVITE_ROLES = ("viewer", "operator")
MAX_OPEN = 50  # open invites per workspace
# Telegram usernames: 5-32 letters, digits and underscores, starting with a letter
TG_USERNAME_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_]{4,31})")


def tg_username(text: str) -> Optional[str]:
    m = TG_USERNAME_RE.fullmatch((text or "").strip())
    return m.group(1).lower() if m else None


def create(db: sqlite3.Connection, ws: int, username: str, role: str, name: str, by: int) -> Dict[str, Any]:
    if role not in INVITE_ROLES:
        raise DLError("member.invite_role")
    now = int(time.time())
    db.execute("DELETE FROM workspace_invites WHERE workspace_id=? AND tg_username=? AND claimed_at IS NULL AND expires_at<=?",
               (ws, username, now))
    if db.execute("SELECT COUNT(*) FROM workspace_invites WHERE workspace_id=? AND claimed_at IS NULL", (ws,)).fetchone()[0] >= MAX_OPEN:
        raise DLError("members.limit")
    try:
        iid = db.execute(
            "INSERT INTO workspace_invites (workspace_id, tg_username, role, display_name, invited_by, created_at, expires_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (ws, username, role, name, by, now, now + INVITE_TTL),
        ).lastrowid
    except sqlite3.IntegrityError:
        raise DLError("member.invite_exists")
    changelog.record(db, ws, "member_invited", "@%s: %s" % (username, role), None, {"invite_id": iid, "role": role})
    return out(db.execute("SELECT * FROM workspace_invites WHERE id=? AND workspace_id=?", (iid, ws)).fetchone())


def out(r: sqlite3.Row) -> Dict[str, Any]:
    return {"id": r["id"], "tg_username": r["tg_username"], "role": r["role"], "name": r["display_name"],
            "created_at": r["created_at"], "expires_at": r["expires_at"], "pending_tg_id": r["pending_tg_id"],
            "pending_name": r["pending_name"], "pending_at": r["pending_at"]}


def list_open(db: sqlite3.Connection, ws: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM workspace_invites WHERE workspace_id=? AND claimed_at IS NULL AND expires_at>? ORDER BY created_at DESC, id DESC",
        (ws, int(time.time())),
    ).fetchall()
    return [out(r) for r in rows]


def cancel(db: sqlite3.Connection, ws: int, invite_id: int) -> None:
    row = db.execute("SELECT * FROM workspace_invites WHERE id=? AND workspace_id=? AND claimed_at IS NULL", (invite_id, ws)).fetchone()
    if not row:
        raise DLError("member.invite_not_found")
    db.execute("DELETE FROM workspace_invites WHERE id=? AND workspace_id=?", (invite_id, ws))
    changelog.record(db, ws, "member_invite_cancelled", "@%s" % row["tg_username"], None, {"invite_id": invite_id})


def request(db: sqlite3.Connection, user_id: Optional[int], tg_id: int, username: Optional[str], name: str,
            only: Optional[int] = None) -> List[Dict[str, Any]]:
    """A person with this Telegram username asks to join the workspaces that invited it. Nothing is granted: the
    inviting workspace's owner approves in the panel, seeing the numeric id. First asker wins until it is rejected.

    `username` must come from Telegram itself (the update or the link token), never from what a person typed."""
    uname = (username or "").strip().lower()
    if not uname:
        return []
    now = int(time.time())
    rows = db.execute(  # ws: token_lookup - the Telegram username names the invites addressed to this person, in any workspace
        "SELECT i.*, w.name AS ws_name FROM workspace_invites i JOIN workspaces w ON w.id=i.workspace_id "
        "WHERE i.tg_username=? AND i.claimed_at IS NULL AND i.pending_tg_id IS NULL AND i.expires_at>? "
        "AND (? IS NULL OR i.id=?) ORDER BY i.id",
        (uname, now, only, only),
    ).fetchall()
    got = []
    for r in rows:
        won = db.execute(
            "UPDATE workspace_invites SET pending_tg_id=?, pending_user_id=?, pending_name=?, pending_at=? "
            "WHERE id=? AND workspace_id=? AND claimed_at IS NULL AND pending_tg_id IS NULL",
            (tg_id, user_id, (name or "")[:64], now, r["id"], r["workspace_id"]),
        ).rowcount
        if won:
            got.append({"id": r["id"], "workspace_id": r["workspace_id"], "workspace": r["ws_name"], "role": r["role"],
                        "invited_by": r["invited_by"]})
    return got


def offers(db: sqlite3.Connection, username: Optional[str]) -> List[sqlite3.Row]:
    """Open invites for this Telegram username that nobody has asked to take yet."""
    name = (username or "").strip().lower()
    if not name:
        return []
    return db.execute(  # ws: token_lookup - which invites name this Telegram username, in any workspace
        "SELECT i.*, w.name AS ws_name, u.name AS by_name, u.username AS by_username FROM workspace_invites i "
        "JOIN workspaces w ON w.id=i.workspace_id LEFT JOIN users u ON u.id=i.invited_by "
        "WHERE i.tg_username=? AND i.claimed_at IS NULL AND i.pending_tg_id IS NULL AND i.expires_at>? ORDER BY i.id",
        (name, int(time.time())),
    ).fetchall()


def approve(db: sqlite3.Connection, ws: int, invite_id: int, by: int) -> Dict[str, Any]:
    """The workspace's owner lets the person who asked in. The account is made now if that Telegram id has none."""
    now = int(time.time())
    row = db.execute("SELECT * FROM workspace_invites WHERE id=? AND workspace_id=? AND claimed_at IS NULL AND expires_at>?",
                     (invite_id, ws, now)).fetchone()
    if not row or row["pending_tg_id"] is None:
        raise DLError("member.invite_not_found")
    tg_id = row["pending_tg_id"]
    user = db.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,)).fetchone() if tg_id else None
    uid = user["id"] if user else row["pending_user_id"]
    if uid is None:
        uid = db.execute("INSERT INTO users (tg_id, tg_username, name, role, created_at) VALUES (?,?,?,'none',?)",
                         (tg_id, row["tg_username"], row["pending_name"] or "", now)).lastrowid
    if db.execute("UPDATE workspace_invites SET claimed_at=?, claimed_by=?, claimed_tg_id=? WHERE id=? AND workspace_id=? AND claimed_at IS NULL",
                  (now, uid, tg_id, invite_id, ws)).rowcount != 1:
        raise DLError("member.invite_not_found")
    added = db.execute(
        "INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role, added_by, display_name, created_at) VALUES (?,?,?,?,?,?)",
        (ws, uid, row["role"], by, row["display_name"], now),
    ).rowcount
    changelog.record(db, ws, "member_invite_claimed", "@%s (%s): %s" % (row["tg_username"], tg_id, row["role"] if added else "-"), None,
                     {"invite_id": invite_id, "user_id": uid, "tg_id": tg_id, "added": bool(added)})
    return {"tg_id": tg_id, "role": row["role"], "added": bool(added)}


def reject(db: sqlite3.Connection, ws: int, invite_id: int) -> None:
    """Clear the request (the invite stays open for the real person); the owner can cancel the invite itself too."""
    n = db.execute("UPDATE workspace_invites SET pending_tg_id=NULL, pending_user_id=NULL, pending_name=NULL, pending_at=NULL "
                   "WHERE id=? AND workspace_id=? AND claimed_at IS NULL AND pending_tg_id IS NOT NULL", (invite_id, ws)).rowcount
    if not n:
        raise DLError("member.invite_not_found")
    changelog.record(db, ws, "member_invite_cancelled", "request #%d rejected" % invite_id, None, {"invite_id": invite_id})
