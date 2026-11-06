import sqlite3
import time
from typing import Optional

from fastapi import Depends, Header, Request

from .db import get_db
from .errors import DLError
from .security import digest

COOKIE = "dl_session"
ROLE_RANK = {"viewer": 1, "admin": 2, "owner": 3}


class Actor:
    """Who is calling: a signed-in user, or an API key acting with a scope."""

    def __init__(self, user_id: Optional[int], role: str, via: str):
        self.user_id, self.role, self.via = user_id, role, via


def current_actor(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: sqlite3.Connection = Depends(get_db),
) -> Actor:
    now = int(time.time())
    if authorization and authorization.lower().startswith("bearer "):
        row = db.execute(
            "SELECT id, scope, created_by FROM api_keys WHERE token_hash=?",
            (digest(authorization[7:].strip()),),
        ).fetchone()
        if not row:
            raise DLError("auth.required")
        db.execute("UPDATE api_keys SET last_used=? WHERE id=?", (now, row["id"]))
        # an 'operate' key is an admin, a 'read' key is a viewer; keys never manage users or other keys
        return Actor(row["created_by"], "admin" if row["scope"] == "operate" else "viewer", "key")
    token = request.cookies.get(COOKIE)
    if token:
        row = db.execute(
            "SELECT u.id, u.role FROM sessions s JOIN users u ON u.id=s.user_id "
            "WHERE s.token_hash=? AND s.expires_at>?",
            (digest(token), now),
        ).fetchone()
        if row:
            return Actor(row["id"], row["role"], "session")
    raise DLError("auth.required")


def require(role: str):
    def check(actor: Actor = Depends(current_actor)) -> Actor:
        if ROLE_RANK[actor.role] < ROLE_RANK[role]:
            raise DLError("auth.forbidden")
        return actor

    return check


def session_only(actor: Actor = Depends(require("viewer"))) -> Actor:
    if actor.via != "session":
        raise DLError("auth.forbidden")
    return actor
