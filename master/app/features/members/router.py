"""Who belongs to the current workspace. Only its owner, signed in (never an API key), manages that."""
import sqlite3
import time
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...db import get_db
from ...deps import Actor, current_workspace, require
from ...errors import DLError
from ...ratelimit import hit
from ...workspaces import ASSIGNABLE, MAX_MEMBERS, is_panel_owner
from ..reports import events as changelog

router = APIRouter(prefix="/members", tags=["members"])
TG_ID_MAX = 10 ** 15  # Telegram user ids are positive and well below this


class MemberOut(BaseModel):
    user_id: int
    name: str
    tg_id: Optional[int]
    tg_username: Optional[str]
    role: str
    last_login: Optional[int]
    added_at: int
    is_me: bool


class MemberCreate(BaseModel):
    tg_id: int
    name: Optional[str] = None
    role: str


class MemberPatch(BaseModel):
    role: str


def _owner(actor: Actor = Depends(require("owner"))) -> Actor:
    if actor.via != "session":
        raise DLError("auth.forbidden")
    return actor


def _role(role: str) -> str:
    if role not in ASSIGNABLE:
        raise DLError("member.role_invalid")
    return role


def _member(db: sqlite3.Connection, ws: int, user_id: int) -> sqlite3.Row:
    row = db.execute(
        "SELECT u.id, u.name, u.tg_id, u.tg_username, u.last_login_at, m.role, m.created_at, m.display_name FROM workspace_members m "
        "JOIN users u ON u.id=m.user_id WHERE m.workspace_id=? AND m.user_id=?",
        (ws, user_id),
    ).fetchone()
    if not row:
        raise DLError("member.not_found")
    return row


def _name(r: sqlite3.Row) -> str:
    """The person's own Telegram name once they have signed in; until then what this workspace's owner called them."""
    own = (r["name"] or "").strip() if r["last_login_at"] else ""
    return own or r["display_name"] or ""


def _out(r: sqlite3.Row, me: Optional[int]) -> dict:
    signed_in = r["last_login_at"] is not None
    return {
        "user_id": r["id"], "name": _name(r), "tg_id": r["tg_id"], "tg_username": r["tg_username"] if signed_in else None,
        "role": r["role"], "last_login": r["last_login_at"], "added_at": r["created_at"], "is_me": r["id"] == me,
    }


def _label(r: sqlite3.Row) -> str:
    return _name(r) or str(r["tg_id"] or r["id"])


@router.get("", response_model=List[MemberOut], operation_id="members_list")
def list_members(actor: Actor = Depends(_owner), ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT u.id, u.name, u.tg_id, u.tg_username, u.last_login_at, m.role, m.created_at, m.display_name FROM workspace_members m "
        "JOIN users u ON u.id=m.user_id WHERE m.workspace_id=? ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 WHEN 'operator' THEN 2 ELSE 3 END, m.created_at, u.id",
        (ws,),
    ).fetchall()
    return [_out(r, actor.user_id) for r in rows]


@router.post("", response_model=MemberOut, status_code=201, operation_id="members_add")
def add_member(body: MemberCreate, actor: Actor = Depends(_owner), ws: int = Depends(current_workspace),
               db: sqlite3.Connection = Depends(get_db)):
    """Add a person by their numeric Telegram id; they sign in with Telegram and see this workspace next to their own.

    Only the panel owner (owner of workspace 1) adds people: every new member can sign in and gets a workspace, so this
    is the registration door of the panel. The answer is the membership only, never the person's profile."""
    if not is_panel_owner(db, actor.user_id):
        raise DLError("members.panel_owner_only")
    hit("members:%d" % actor.user_id, 30, 3600)
    role = _role(body.role)
    if not 0 < body.tg_id < TG_ID_MAX:
        raise DLError("member.tg_id_invalid")
    name = (body.name or "").strip()
    if len(name) > 64:
        raise DLError("member.name_invalid")
    now = int(time.time())
    if db.execute("SELECT COUNT(*) FROM workspace_members WHERE workspace_id=?", (ws,)).fetchone()[0] >= MAX_MEMBERS:
        raise DLError("members.limit")
    user = db.execute("SELECT id FROM users WHERE tg_id=?", (body.tg_id,)).fetchone()
    if user is None:  # no profile data from an invite: the name stays on this membership only
        uid = db.execute("INSERT INTO users (tg_id, name, role, created_at) VALUES (?,'','none',?)", (body.tg_id, now)).lastrowid
    else:
        uid = user["id"]
        if db.execute("SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=?", (ws, uid)).fetchone():
            raise DLError("member.exists")
    db.execute(
        "INSERT INTO workspace_members (workspace_id, user_id, role, added_by, display_name, created_at) VALUES (?,?,?,?,?,?)",
        (ws, uid, role, actor.user_id, name, now),
    )
    label = name or str(body.tg_id)
    changelog.record(db, ws, "member_added", "%s: %s" % (label, role), None, {"user_id": uid, "role": role})
    return {"user_id": uid, "name": name, "tg_id": body.tg_id, "tg_username": None, "role": role, "last_login": None,
            "added_at": now, "is_me": uid == actor.user_id}


@router.patch("/{user_id}", response_model=MemberOut, operation_id="members_update")
def update_member(user_id: int, body: MemberPatch, actor: Actor = Depends(_owner), ws: int = Depends(current_workspace),
                  db: sqlite3.Connection = Depends(get_db)):
    hit("members:%d" % actor.user_id, 30, 3600)
    row = _member(db, ws, user_id)
    role = _role(body.role)
    if row["role"] == "owner":
        raise DLError("member.owner_locked")
    if user_id == actor.user_id:
        raise DLError("member.self")
    if role != row["role"]:
        db.execute("UPDATE workspace_members SET role=? WHERE workspace_id=? AND user_id=?", (role, ws, user_id))
        changelog.record(db, ws, "member_role_changed", "%s: %s -> %s" % (_label(row), row["role"], role), None,
                         {"user_id": user_id, "old": row["role"], "new": role})
    return _out(_member(db, ws, user_id), actor.user_id)


@router.delete("/{user_id}", status_code=204, operation_id="members_remove")
def remove_member(user_id: int, actor: Actor = Depends(_owner), ws: int = Depends(current_workspace),
                  db: sqlite3.Connection = Depends(get_db)):
    """Take a person out of this workspace; their own workspace and other memberships stay as they are."""
    hit("members:%d" % actor.user_id, 30, 3600)
    row = _member(db, ws, user_id)
    if row["role"] == "owner":
        raise DLError("member.owner_locked")
    if user_id == actor.user_id:
        raise DLError("member.self")
    db.execute("DELETE FROM workspace_members WHERE workspace_id=? AND user_id=?", (ws, user_id))
    # their sessions here move to another workspace on the next request; with none left, they end
    db.execute("UPDATE sessions SET active_workspace_id=NULL WHERE user_id=? AND active_workspace_id=?", (user_id, ws))
    if not db.execute("SELECT 1 FROM workspace_members WHERE user_id=?", (user_id,)).fetchone():
        db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM api_keys WHERE workspace_id=? AND created_by=?", (ws, user_id))
    changelog.record(db, ws, "member_removed", "%s: %s" % (_label(row), row["role"]), None, {"user_id": user_id, "role": row["role"]})
