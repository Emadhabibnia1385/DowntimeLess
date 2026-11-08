import sqlite3
import time
from typing import Optional

from fastapi import Depends, Header, Request

from .db import get_db
from .errors import DLError
from .security import digest
from .workspaces import default_workspace, member_role

COOKIE = "dl_session"
ROLE_RANK = {"viewer": 1, "operator": 2, "admin": 3, "owner": 4}


class Actor:
    """Who is calling, inside which workspace and with which role there: a signed-in user, or an API key."""

    def __init__(self, user_id: Optional[int], role: str, via: str, workspace_id: int, full: bool = False,
                 session_id: Optional[int] = None):
        self.user_id, self.role, self.via, self.full = user_id, role, via, full
        self.workspace_id, self.session_id = workspace_id, session_id


def current_actor(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: sqlite3.Connection = Depends(get_db),
) -> Actor:
    now = int(time.time())
    if authorization and authorization.lower().startswith("bearer "):
        row = db.execute(  # ws: the key's hash names one key, and with it the only workspace it may act in
            "SELECT k.id, k.scope, k.created_by, k.workspace_id FROM api_keys k JOIN workspaces w ON w.id=k.workspace_id "
            "WHERE k.token_hash=?",
            (digest(authorization[7:].strip()),),
        ).fetchone()
        if not row:
            raise DLError("auth.required")
        db.execute("UPDATE api_keys SET last_used=? WHERE id=? AND workspace_id=?", (now, row["id"], row["workspace_id"]))
        # a key acts only inside its own workspace: 'full' does what the owner does there, 'read' only looks.
        # Passwords, members and one's own profile stay with a signed-in person (session_only).
        if row["scope"] == "full":
            return Actor(row["created_by"], "owner", "key", row["workspace_id"], full=True)
        return Actor(row["created_by"], "viewer", "key", row["workspace_id"])
    token = request.cookies.get(COOKIE)
    if token:
        row = db.execute(
            "SELECT s.id AS sid, s.active_workspace_id, u.id FROM sessions s JOIN users u ON u.id=s.user_id "
            "WHERE s.token_hash=? AND s.expires_at>?",
            (digest(token), now),
        ).fetchone()
        if row:
            ws = row["active_workspace_id"]
            role = member_role(db, ws, row["id"]) if ws else None
            if role is None:  # removed from that workspace, or a session from before workspaces: move on
                ws = default_workspace(db, row["id"])
                role = member_role(db, ws, row["id"]) if ws else None
                if role is None:
                    raise DLError("auth.required")
                db.execute("UPDATE sessions SET active_workspace_id=? WHERE id=?", (ws, row["sid"]))
            return Actor(row["id"], role, "session", ws, session_id=row["sid"])
    raise DLError("auth.required")


def require(role: str):
    def check(actor: Actor = Depends(current_actor)) -> Actor:
        if ROLE_RANK[actor.role] < ROLE_RANK[role]:
            raise DLError("auth.forbidden")
        return actor

    return check


def current_workspace(actor: Actor = Depends(current_actor)) -> int:
    """The workspace every query of a data route is scoped to. Every data route takes it (a test checks)."""
    return actor.workspace_id


def session_only(actor: Actor = Depends(require("viewer"))) -> Actor:
    if actor.via != "session":
        raise DLError("auth.forbidden")
    return actor
