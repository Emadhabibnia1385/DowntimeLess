"""Who belongs to the current workspace. Only its owner, signed in (never an API key), manages that."""
import sqlite3
import time
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ... import appsettings, invites
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
    # a numeric Telegram id or the username of an account of this panel (a Telegram @username is POST /members/invites)
    who: Optional[str] = None
    tg_id: Optional[int] = None  # the older form of a numeric id
    name: Optional[str] = None
    role: str


class InviteOut(BaseModel):
    id: int
    tg_username: str
    role: str
    name: str
    created_at: int
    expires_at: int


class InviteCreate(BaseModel):
    tg_username: str  # with or without @
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


def _may_add_new_people(db: sqlite3.Connection, actor: Actor) -> None:
    """New people can sign in and get a workspace: while registration is closed only the panel owner lets them in."""
    if not appsettings.registration_open(db) and not is_panel_owner(db, actor.user_id):
        raise DLError("members.panel_owner_only")


def _join(db: sqlite3.Connection, ws: int, uid: int, role: str, actor: Actor, name: str, label: str, now: int) -> dict:
    if db.execute("SELECT COUNT(*) FROM workspace_members WHERE workspace_id=?", (ws,)).fetchone()[0] >= MAX_MEMBERS:
        raise DLError("members.limit")
    if db.execute("SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=?", (ws, uid)).fetchone():
        raise DLError("member.exists")
    db.execute(
        "INSERT INTO workspace_members (workspace_id, user_id, role, added_by, display_name, created_at) VALUES (?,?,?,?,?,?)",
        (ws, uid, role, actor.user_id, name, now),
    )
    changelog.record(db, ws, "member_added", "%s: %s" % (label, role), None, {"user_id": uid, "role": role})
    tg_id = db.execute("SELECT tg_id FROM users WHERE id=?", (uid,)).fetchone()["tg_id"]
    return {"user_id": uid, "name": name, "tg_id": tg_id if label.isdigit() else None, "tg_username": None, "role": role,
            "last_login": None, "added_at": now, "is_me": uid == actor.user_id}


@router.post("", response_model=MemberOut, status_code=201, operation_id="members_add")
def add_member(body: MemberCreate, actor: Actor = Depends(_owner), ws: int = Depends(current_workspace),
               db: sqlite3.Connection = Depends(get_db)):
    """Add a person now by numeric Telegram id or by the username of an account of this panel; they see this workspace
    next to their own. A new Telegram id is a new person: while registration is closed only the panel owner adds one.
    The answer is the membership only, never the person's profile."""
    hit("members:%d" % actor.user_id, 30, 3600)
    role = _role(body.role)
    name = (body.name or "").strip()
    if len(name) > 64:
        raise DLError("member.name_invalid")
    who = (body.who or "").strip()
    now = int(time.time())
    if body.tg_id is not None or who.lstrip("-").isdigit():
        tg_id = body.tg_id if body.tg_id is not None else int(who)
        if not 0 < tg_id < TG_ID_MAX:
            raise DLError("member.tg_id_invalid")
        user = db.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,)).fetchone()
        if user is None:  # no profile data from an invite: the name stays on this membership only
            _may_add_new_people(db, actor)
            uid = db.execute("INSERT INTO users (tg_id, name, role, created_at) VALUES (?,'','none',?)", (tg_id, now)).lastrowid
        else:
            uid = user["id"]
        return _join(db, ws, uid, role, actor, name, str(tg_id), now)
    account = who.lower()
    if not (3 <= len(account) <= 64 and account.isprintable() and " " not in account):
        raise DLError("member.who_invalid")
    user = db.execute("SELECT id FROM users WHERE username=?", (account,)).fetchone()
    if user is None:
        raise DLError("member.account_not_found")
    return _join(db, ws, user["id"], role, actor, name, account, now)


@router.post("/invites", response_model=InviteOut, status_code=201, operation_id="members_invite")
def invite(body: InviteCreate, actor: Actor = Depends(_owner), ws: int = Depends(current_workspace),
           db: sqlite3.Connection = Depends(get_db)):
    """Invite a Telegram @username for 14 days, as viewer or operator. The person with that username claims it by starting
    the bot or linking Telegram to their account; the inviter is then told in Telegram who claimed it (numeric id)."""
    hit("members:%d" % actor.user_id, 30, 3600)
    role = _role(body.role)
    name = (body.name or "").strip()
    if len(name) > 64:
        raise DLError("member.name_invalid")
    raw = body.tg_username.strip()
    username = invites.tg_username(raw if raw.startswith("@") else "@" + raw)
    if not username:
        raise DLError("member.who_invalid")
    _may_add_new_people(db, actor)
    return invites.create(db, ws, username, role, name, actor.user_id)


@router.get("/invites", response_model=List[InviteOut], operation_id="members_invites")
def list_invites(actor: Actor = Depends(_owner), ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    """Open invites of this workspace by Telegram username."""
    return invites.list_open(db, ws)


@router.delete("/invites/{invite_id}", status_code=204, operation_id="members_cancel_invite")
def cancel_invite(invite_id: int, actor: Actor = Depends(_owner), ws: int = Depends(current_workspace),
                  db: sqlite3.Connection = Depends(get_db)):
    hit("members:%d" % actor.user_id, 30, 3600)
    invites.cancel(db, ws, invite_id)


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
