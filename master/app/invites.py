"""Invites by Telegram username: a pending membership that the person with that username claims by starting the bot
or by linking Telegram to their account.

A Telegram username can change hands, so an invite is a weaker proof than a numeric id: it grants at most `operator`,
lives 14 days, is claimed once, and the inviter is told in Telegram who claimed it (numeric id and name), so a squatter
is seen and removed. A claim never changes an existing membership (no promotion, no demotion)."""
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
            "created_at": r["created_at"], "expires_at": r["expires_at"]}


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


def claim(db: sqlite3.Connection, user_id: int, tg_id: int, username: Optional[str]) -> List[Dict[str, Any]]:
    """Turn the open invites for this Telegram username into memberships of `user_id`, each exactly once.

    `username` must come from Telegram itself (the update or the link token), never from what a person typed."""
    name = (username or "").strip().lower()
    if not name:
        return []
    now = int(time.time())
    rows = db.execute(  # ws: token_lookup - the Telegram username names the invites addressed to this person, in any workspace
        "SELECT i.*, w.name AS ws_name FROM workspace_invites i JOIN workspaces w ON w.id=i.workspace_id "
        "WHERE i.tg_username=? AND i.claimed_at IS NULL AND i.expires_at>? ORDER BY i.id",
        (name, now),
    ).fetchall()
    got = []
    for r in rows:
        won = db.execute(
            "UPDATE workspace_invites SET claimed_at=?, claimed_by=?, claimed_tg_id=? WHERE id=? AND workspace_id=? AND claimed_at IS NULL",
            (now, user_id, tg_id, r["id"], r["workspace_id"]),
        ).rowcount
        if not won:
            continue
        added = db.execute(
            "INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role, added_by, display_name, created_at) VALUES (?,?,?,?,?,?)",
            (r["workspace_id"], user_id, r["role"], r["invited_by"], r["display_name"], now),
        ).rowcount
        changelog.record(db, r["workspace_id"], "member_invite_claimed", "@%s (%d): %s" % (name, tg_id, r["role"] if added else "-"), None,
                         {"invite_id": r["id"], "user_id": user_id, "tg_id": tg_id, "added": bool(added)})
        got.append({"workspace_id": r["workspace_id"], "workspace": r["ws_name"], "role": r["role"], "added": bool(added),
                    "invited_by": r["invited_by"]})
    return got


def has_open(db: sqlite3.Connection, username: Optional[str]) -> bool:
    name = (username or "").strip().lower()
    return bool(name) and db.execute(  # ws: token_lookup - does any open invite name this Telegram username
        "SELECT 1 FROM workspace_invites WHERE tg_username=? AND claimed_at IS NULL AND expires_at>?", (name, int(time.time()))
    ).fetchone() is not None
