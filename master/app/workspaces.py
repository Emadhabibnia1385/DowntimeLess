"""Workspaces: who belongs where, which one a session acts in, and the scoped lookups every route uses."""
import sqlite3
import time
from typing import Any, Dict, List, Optional

from .errors import DLError

ROLES = ("viewer", "operator", "admin", "owner")
ASSIGNABLE = ("viewer", "operator", "admin")  # one owner per workspace; transfer is not offered
PERSONAL_FALLBACK = "فضای کار شخصی"
PANEL_WORKSPACE = 1  # the installer's workspace; its owner is the panel owner
MAX_MEMBERS = 50
MAX_SERVERS = 200
MAX_DOMAINS = 300
SELF_SERVERS, SELF_DOMAINS = 20, 30  # caps of a workspace made by self-registration
ROLE_RANK = {"viewer": 1, "operator": 2, "admin": 3, "owner": 4}


def server_cap(db: sqlite3.Connection, ws: int) -> int:
    row = db.execute("SELECT server_cap FROM workspaces WHERE id=?", (ws,)).fetchone()
    return row["server_cap"] if row and row["server_cap"] is not None else MAX_SERVERS


def domain_cap(db: sqlite3.Connection, ws: int) -> int:
    row = db.execute("SELECT domain_cap FROM workspaces WHERE id=?", (ws,)).fetchone()
    return row["domain_cap"] if row and row["domain_cap"] is not None else MAX_DOMAINS


def panel_owner_id(db: sqlite3.Connection) -> Optional[int]:
    """Whoever claimed the panel: the owner of workspace 1. Only they let new people in."""
    row = db.execute("SELECT owner_user_id FROM workspaces WHERE id=?", (PANEL_WORKSPACE,)).fetchone()
    return row["owner_user_id"] if row else None


def is_panel_owner(db: sqlite3.Connection, user_id: Optional[int]) -> bool:
    return user_id is not None and panel_owner_id(db) == user_id


def user_label(db: sqlite3.Connection, user_id: Optional[int]) -> Optional[str]:
    """How a person is shown to others: their own Telegram name, else @username, else their Telegram id."""
    if user_id is None:
        return None
    row = db.execute("SELECT name, tg_username, tg_id FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        return None
    name = (row["name"] or "").strip() or ("@" + row["tg_username"] if row["tg_username"] else "")
    return name or (str(row["tg_id"]) if row["tg_id"] else None)


def member_role(db: sqlite3.Connection, ws: int, user_id: int) -> Optional[str]:
    row = db.execute("SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?", (ws, user_id)).fetchone()
    return row["role"] if row else None


def is_member_anywhere(db: sqlite3.Connection, user_id: int) -> bool:
    return db.execute("SELECT 1 FROM workspace_members WHERE user_id=?", (user_id,)).fetchone() is not None


def default_workspace(db: sqlite3.Connection, user_id: int) -> Optional[int]:
    """Where a sign-in lands: the workspace used last (while still a member), else the one they own, else the first
    membership. A workspace someone joined them to since never takes over on its own."""
    last = db.execute(
        "SELECT u.last_workspace_id FROM users u JOIN workspace_members m ON m.workspace_id=u.last_workspace_id AND m.user_id=u.id "
        "WHERE u.id=?",
        (user_id,),
    ).fetchone()
    if last:
        return last["last_workspace_id"]
    row = db.execute(
        "SELECT m.workspace_id FROM workspace_members m JOIN workspaces w ON w.id=m.workspace_id "
        "WHERE m.user_id=? ORDER BY (w.owner_user_id IS NOT m.user_id), m.created_at, m.workspace_id LIMIT 1",
        (user_id,),
    ).fetchone()
    return row["workspace_id"] if row else None


def ensure_personal(db: sqlite3.Connection, user: sqlite3.Row, caps: Optional[tuple] = None) -> int:
    """The person's own workspace, created empty (and only once) the first time they sign in. `caps` (servers, domains)
    is set for a self-registered account; one statement both checks and inserts, so two sign-ins never make two."""
    now = int(time.time())
    name = (user["name"] or "").strip() or ("@" + user["tg_username"] if user["tg_username"] else "")
    name = name or (user["username"] if "username" in user.keys() and user["username"] else PERSONAL_FALLBACK)
    servers, domains = caps or (None, None)
    made = db.execute(
        "INSERT INTO workspaces (name, owner_user_id, created_at, server_cap, domain_cap) SELECT ?,?,?,?,? "
        "WHERE NOT EXISTS (SELECT 1 FROM workspaces WHERE owner_user_id=?)",
        (name[:64], user["id"], now, servers, domains, user["id"]),
    )
    if not made.rowcount:
        return db.execute("SELECT id FROM workspaces WHERE owner_user_id=? ORDER BY id LIMIT 1", (user["id"],)).fetchone()["id"]
    ws = made.lastrowid
    db.execute(
        "INSERT INTO workspace_members (workspace_id, user_id, role, added_by, created_at) VALUES (?,?,'owner',?,?)",
        (ws, user["id"], user["id"], now),
    )
    return ws


def list_for_user(db: sqlite3.Connection, user_id: int) -> List[Dict[str, Any]]:
    rows = db.execute(
        "SELECT w.id, w.name, w.owner_user_id, m.role, m.added_by FROM workspace_members m JOIN workspaces w ON w.id=m.workspace_id "
        "WHERE m.user_id=? ORDER BY (w.owner_user_id IS NOT m.user_id), m.created_at, w.id",
        (user_id,),
    ).fetchall()
    return [_space(db, r, user_id) for r in rows]


def _space(db: sqlite3.Connection, r: sqlite3.Row, user_id: int) -> Dict[str, Any]:
    mine = r["owner_user_id"] == user_id
    # who let me in: shown next to a workspace that is not mine, so a lookalike name cannot pass for my own
    inviter = None if mine else user_label(db, r["added_by"] or r["owner_user_id"])
    return {"id": r["id"], "name": r["name"], "role": r["role"], "is_personal": mine, "invited_by": inviter}


def workspace_out(db: sqlite3.Connection, ws: int, user_id: int) -> Dict[str, Any]:
    row = db.execute(
        "SELECT w.id, w.name, w.owner_user_id, m.role, m.added_by FROM workspaces w "
        "JOIN workspace_members m ON m.workspace_id=w.id AND m.user_id=? WHERE w.id=?",
        (user_id, ws),
    ).fetchone()
    if not row:
        raise DLError("workspace.not_found")
    return _space(db, row, user_id)


def server_row(db: sqlite3.Connection, ws: int, server_id: int) -> sqlite3.Row:
    """A server of this workspace; one of another workspace does not exist here (404, never 403)."""
    row = db.execute("SELECT * FROM servers WHERE id=? AND workspace_id=?", (server_id, ws)).fetchone()
    if not row:
        raise DLError("server.not_found")
    return row
