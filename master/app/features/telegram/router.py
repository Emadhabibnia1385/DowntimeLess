import re
import sqlite3
import time
from typing import Dict, List

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...alerts import routes, valid_route
from ...db import get_db
from ...deps import Actor, current_workspace, require
from ...errors import DLError
from ..settings.router import RULES

router = APIRouter(prefix="/telegram", tags=["telegram"])

_NUMERIC = re.compile(r"^-?\d{5,16}$")
_USERNAME = re.compile(r"^@[A-Za-z][A-Za-z0-9_]{4,31}$")
_LINK = re.compile(r"^(?:https?://)?t\.me/([A-Za-z][A-Za-z0-9_]{4,31})/?$")


class ChannelIn(BaseModel):
    name: str
    chat_id: str


class ChannelOut(BaseModel):
    id: int
    name: str
    chat_id: str
    created_at: int


def normalize_chat_id(raw: str) -> str:
    """A numeric chat id (-100...) or an @username; a t.me link becomes the username."""
    value = raw.strip()
    link = _LINK.match(value)
    if link:
        value = "@" + link.group(1)
    if not (_NUMERIC.match(value) or _USERNAME.match(value)):
        raise DLError("channel.invalid")
    return value


def _out(r: sqlite3.Row) -> Dict[str, object]:
    return {"id": r["id"], "name": r["name"], "chat_id": r["chat_id"], "created_at": r["created_at"]}


def _channel(db: sqlite3.Connection, ws: int, channel_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM telegram_channels WHERE id=? AND workspace_id=?", (channel_id, ws)).fetchone()
    if not row:
        raise DLError("channel.not_found")
    return row


@router.get("/channels", response_model=List[ChannelOut], operation_id="telegram_list_channels")
def list_channels(_: Actor = Depends(require("admin")), ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    return [_out(r) for r in db.execute("SELECT * FROM telegram_channels WHERE workspace_id=? ORDER BY id", (ws,))]


@router.post("/channels", response_model=ChannelOut, status_code=201, operation_id="telegram_create_channel")
def create_channel(body: ChannelIn, request: Request, actor: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
                   db: sqlite3.Connection = Depends(get_db)):
    """A chat the shared bot may post this workspace's alerts to, checked with Telegram before it is saved.

    A group or channel: the bot must be an administrator that may post, and so must the caller (with the Telegram account
    linked to their panel account). A private chat (a positive id): only the caller's own id. One chat, one workspace."""
    name, chat_id = body.name.strip(), normalize_chat_id(body.chat_id)
    if not name or len(name) > 64:
        raise DLError("channel.invalid")
    if db.execute("SELECT 1 FROM telegram_channels WHERE workspace_id=? AND chat_id=?", (ws, chat_id)).fetchone():
        raise DLError("channel.exists")
    # another workspace's chat: the same answer as a malformed id, so nobody learns which chats are taken
    if db.execute("SELECT 1 FROM telegram_channels WHERE chat_id=?", (chat_id,)).fetchone():  # ws: unique_check - one chat in one workspace
        raise DLError("channel.invalid")
    # only the caller's own Telegram account proves a chat: a member added without being asked must never make their
    # private chat or their channel a target for someone else's alerts
    me = db.execute("SELECT tg_id FROM users WHERE id=?", (actor.user_id,)).fetchone()
    managers = {me["tg_id"]} if me and me["tg_id"] is not None else set()
    if _NUMERIC.match(chat_id) and not chat_id.startswith("-"):
        if int(chat_id) not in managers:
            raise DLError("channel.private_not_member")
    else:
        tg = getattr(request.app.state, "tg", None)
        if tg is None:
            raise DLError("bot.not_configured")
        if not _verified(tg, int(chat_id) if _NUMERIC.match(chat_id) else chat_id, managers):
            raise DLError("channel.not_verified")
    now = int(time.time())
    try:
        cur = db.execute(
            "INSERT INTO telegram_channels (workspace_id, name, chat_id, created_at, verified_at) VALUES (?,?,?,?,?)",
            (ws, name, chat_id, now, now),
        )
    except sqlite3.IntegrityError:
        raise DLError("channel.invalid")
    return _out(_channel(db, ws, cur.lastrowid))


def _verified(tg, chat, managers) -> bool:
    """The bot administers the chat with the right to post, and so does one of the workspace's owner or admins."""
    admins = tg.chat_admins(chat)
    if not admins:
        return False
    try:
        me = tg.bot_id()
    except Exception:
        return False
    ids = {a.get("user", {}).get("id") for a in admins}
    bot = next((a for a in admins if a.get("user", {}).get("id") == me), None)
    can_post = bot is not None and bot.get("can_post_messages", True) is not False
    return can_post and bool(ids & managers)


@router.delete("/channels/{channel_id}", status_code=204, operation_id="telegram_delete_channel")
def delete_channel(channel_id: int, _: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
                   db: sqlite3.Connection = Depends(get_db)):
    _channel(db, ws, channel_id)
    # those alerts go back to their default
    db.execute("DELETE FROM rule_routes WHERE workspace_id=? AND route=?", (ws, "channel:%d" % channel_id))
    db.execute("DELETE FROM telegram_channels WHERE id=? AND workspace_id=?", (channel_id, ws))


@router.post("/channels/{channel_id}/test", status_code=204, operation_id="telegram_test_channel")
def test_channel(channel_id: int, request: Request, _: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
                 db: sqlite3.Connection = Depends(get_db)):
    """Send one message through the bot; the bot token never leaves the server."""
    row = _channel(db, ws, channel_id)
    if not row["verified_at"]:
        raise DLError("channel.not_verified")
    tg = getattr(request.app.state, "tg", None)
    if tg is None:
        raise DLError("bot.not_configured")
    chat = int(row["chat_id"]) if _NUMERIC.match(row["chat_id"]) else row["chat_id"]
    if tg.send(chat, "✅ <b>DowntimeLess</b>: پیام آزمایشی؛ اعلان‌ها به این کانال می‌آیند.") is False:
        raise DLError("telegram.send_failed")


@router.get("/routes", response_model=Dict[str, str], operation_id="telegram_get_routes")
def get_routes(_: Actor = Depends(require("admin")), ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    return routes(db, ws)


@router.put("/routes", response_model=Dict[str, str], operation_id="telegram_put_routes")
def put_routes(body: Dict[str, str], _: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
               db: sqlite3.Connection = Depends(get_db)):
    for rule, route in body.items():
        if rule not in RULES:
            raise DLError("route.unknown_rule")
        if route.startswith("channel:"):
            if not valid_route(db, ws, route):
                raise DLError("route.unknown_channel")
        elif route not in ("panel", "admins"):
            raise DLError("route.invalid")
    for rule, route in body.items():
        db.execute(
            "INSERT INTO rule_routes (workspace_id, rule, route) VALUES (?,?,?) ON CONFLICT(workspace_id, rule) DO UPDATE SET route=excluded.route",
            (ws, rule, route),
        )
    return routes(db, ws)
