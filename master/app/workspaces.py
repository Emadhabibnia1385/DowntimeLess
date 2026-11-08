"""Workspaces: who belongs where, which one a session acts in, and the scoped lookups every route uses."""
import sqlite3
import time
from typing import Any, Dict, List, Optional

from .errors import DLError

ROLES = ("viewer", "operator", "admin", "owner")
ASSIGNABLE = ("viewer", "operator", "admin")  # one owner per workspace; transfer is not offered
PERSONAL_FALLBACK = "فضای کار شخصی"


def member_role(db: sqlite3.Connection, ws: int, user_id: int) -> Optional[str]:
    row = db.execute("SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?", (ws, user_id)).fetchone()
    return row["role"] if row else None


def is_member_anywhere(db: sqlite3.Connection, user_id: int) -> bool:
    return db.execute("SELECT 1 FROM workspace_members WHERE user_id=?", (user_id,)).fetchone() is not None


def default_workspace(db: sqlite3.Connection, user_id: int) -> Optional[int]:
    """The last one used while still a member; else the first one they were invited to; else their own."""
    last = db.execute(
        "SELECT u.last_workspace_id FROM users u JOIN workspace_members m ON m.workspace_id=u.last_workspace_id AND m.user_id=u.id "
        "WHERE u.id=?",
        (user_id,),
    ).fetchone()
    if last:
        return last["last_workspace_id"]
    row = db.execute(
        "SELECT m.workspace_id FROM workspace_members m JOIN workspaces w ON w.id=m.workspace_id "
        "WHERE m.user_id=? ORDER BY (w.owner_user_id IS m.user_id), m.created_at, m.workspace_id LIMIT 1",
        (user_id,),
    ).fetchone()
    return row["workspace_id"] if row else None


def ensure_personal(db: sqlite3.Connection, user: sqlite3.Row) -> int:
    """The person's own workspace, created empty (and only once) the first time they sign in."""
    row = db.execute("SELECT id FROM workspaces WHERE owner_user_id=? ORDER BY id LIMIT 1", (user["id"],)).fetchone()
    if row:
        return row["id"]
    now = int(time.time())
    name = (user["name"] or "").strip() or ("@" + user["tg_username"] if user["tg_username"] else PERSONAL_FALLBACK)
    try:
        ws = db.execute("INSERT INTO workspaces (name, owner_user_id, created_at) VALUES (?,?,?)", (name[:64], user["id"], now)).lastrowid
    except sqlite3.IntegrityError:  # a second sign-in at the same moment made it first
        return db.execute("SELECT id FROM workspaces WHERE owner_user_id=?", (user["id"],)).fetchone()["id"]
    db.execute(
        "INSERT INTO workspace_members (workspace_id, user_id, role, added_by, created_at) VALUES (?,?,'owner',?,?)",
        (ws, user["id"], user["id"], now),
    )
    return ws


def list_for_user(db: sqlite3.Connection, user_id: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        "SELECT w.id, w.name, w.owner_user_id, m.role FROM workspace_members m JOIN workspaces w ON w.id=m.workspace_id "
        "WHERE m.user_id=? ORDER BY (w.owner_user_id IS NOT m.user_id), m.created_at, w.id",
        (user_id,),
    ).fetchall()
    return [{"id": r["id"], "name": r["name"], "role": r["role"], "is_personal": r["owner_user_id"] == user_id} for r in rows]


def workspace_out(db: sqlite3.Connection, ws: int, user_id: int) -> Dict[str, Any]:
    row = db.execute(
        "SELECT w.id, w.name, w.owner_user_id, m.role FROM workspaces w JOIN workspace_members m ON m.workspace_id=w.id AND m.user_id=? "
        "WHERE w.id=?",
        (user_id, ws),
    ).fetchone()
    if not row:
        raise DLError("workspace.not_found")
    return {"id": row["id"], "name": row["name"], "role": row["role"], "is_personal": row["owner_user_id"] == user_id}


def server_row(db: sqlite3.Connection, ws: int, server_id: int) -> sqlite3.Row:
    """A server of this workspace; one of another workspace does not exist here (404, never 403)."""
    row = db.execute("SELECT * FROM servers WHERE id=? AND workspace_id=?", (server_id, ws)).fetchone()
    if not row:
        raise DLError("server.not_found")
    return row
