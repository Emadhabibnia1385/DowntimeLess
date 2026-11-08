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


HEADER = "X-Workspace-Id"


def _header_ws(request: Request) -> Optional[int]:
    """The workspace a browser tab names on each request; anything that is not a positive id is not a workspace."""
    raw = request.headers.get(HEADER)
    if raw is None or raw == "":
        return None
    if not raw.isdigit() or int(raw) <= 0:
        raise DLError("workspace.not_found")
    return int(raw)


def _cap(scope_role: str, member: Optional[str]) -> Optional[str]:
    """A key never acts above what its creator may do in that workspace today."""
    if member is None:
        return None
    return scope_role if ROLE_RANK[scope_role] <= ROLE_RANK[member] else member


def resolve(request: Request, authorization: Optional[str], db: sqlite3.Connection, use_header: bool) -> Actor:
    now = int(time.time())
    wanted = _header_ws(request) if use_header else None
    if authorization and authorization.lower().startswith("bearer "):
        row = db.execute(  # ws: token_lookup - the key's hash names one key, and with it the only workspace it may act in
            "SELECT k.id, k.scope, k.created_by, k.workspace_id FROM api_keys k JOIN workspaces w ON w.id=k.workspace_id "
            "WHERE k.token_hash=?",
            (digest(authorization[7:].strip()),),
        ).fetchone()
        if not row:
            raise DLError("auth.required")
        ws = row["workspace_id"]
        if wanted is not None and wanted != ws:
            raise DLError("workspace.not_found")
        # 'full' does what the owner does there and 'read' only looks, but never more than the creator's role now
        role = _cap("owner" if row["scope"] == "full" else "viewer", member_role(db, ws, row["created_by"]))
        if role is None:
            raise DLError("auth.required")
        db.execute("UPDATE api_keys SET last_used=? WHERE id=? AND workspace_id=?", (now, row["id"], ws))
        return Actor(row["created_by"], role, "key", ws, full=row["scope"] == "full")
    token = request.cookies.get(COOKIE)
    if token:
        row = db.execute(
            "SELECT s.id AS sid, s.active_workspace_id, u.id FROM sessions s JOIN users u ON u.id=s.user_id "
            "WHERE s.token_hash=? AND s.expires_at>?",
            (digest(token), now),
        ).fetchone()
        if row:
            if wanted is not None:  # the tab's workspace: a membership checked on every request, never a fallback
                role = member_role(db, wanted, row["id"])
                if role is None:
                    raise DLError("workspace.not_found")
                return Actor(row["id"], role, "session", wanted, session_id=row["sid"])
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


def current_actor(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: sqlite3.Connection = Depends(get_db),
) -> Actor:
    """Who is calling and in which workspace: the tab's X-Workspace-Id when sent, else the session's (or the key's)."""
    return resolve(request, authorization, db, use_header=True)


def any_workspace_actor(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: sqlite3.Connection = Depends(get_db),
) -> Actor:
    """The same person, ignoring the tab's header: listing and switching workspaces must work from a stale tab."""
    return resolve(request, authorization, db, use_header=False)


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


def session_any_workspace(actor: Actor = Depends(any_workspace_actor)) -> Actor:
    if actor.via != "session":
        raise DLError("auth.forbidden")
    return actor
