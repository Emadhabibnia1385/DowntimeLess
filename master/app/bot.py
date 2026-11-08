import logging
import threading
import time
from html import escape
from typing import Any, Dict

from .db import connect
from .features.auth import service as auth
from .settings import get_settings
from .telegram import Telegram

log = logging.getLogger("dl.bot")


def _name(frm: Dict[str, Any]) -> str:
    return (frm.get("first_name", "") + " " + frm.get("last_name", "")).strip() or frm.get("username", "")


def handle(tg: Telegram, update: Dict[str, Any]) -> None:
    db = connect()
    try:
        if "callback_query" in update:
            _callback(tg, db, update["callback_query"])
        elif "message" in update and update["message"].get("text"):
            _message(tg, db, update["message"])
    finally:
        db.close()


def _message(tg: Telegram, db, msg: Dict[str, Any]) -> None:
    frm, chat, text = msg["from"], msg["chat"]["id"], msg["text"].strip()
    arg = text.split(" ", 1)[1].strip() if text.startswith("/start ") else ""
    if arg.startswith("claim_"):
        ok = auth.claim_owner(db, arg[6:], frm["id"], _name(frm), frm.get("username"))
        tg.send(chat, "✅ شما مالک این پنل شدید. حالا از پنل وب وارد شوید." if ok else "⛔ این لینک نامعتبر است یا قبلاً استفاده شده.")
    elif arg.startswith("wl_"):
        res = auth.link_challenge(db, arg[3:], frm["id"])
        if not res:
            tg.send(chat, "⛔ درخواست ورود پیدا نشد یا منقضی شده است.")
        elif res[1] is None:
            tg.send(chat, "⛔ این حساب تلگرام در پنل ثبت نشده است. از مالک پنل بخواهید شما را اضافه کند.")
        else:
            ch = res[0]
            # someone added by Telegram id alone gets the name Telegram knows, for the member list and their own workspace
            db.execute("UPDATE users SET name=? WHERE id=? AND name=''", (_name(frm)[:64], res[1]["id"]))
            db.execute("UPDATE users SET tg_username=? WHERE id=? AND tg_username IS NULL", (frm.get("username"), res[1]["id"]))
            tg.send(
                chat,
                "🔐 <b>درخواست ورود به پنل</b>\nآی‌پی: <code>%s</code>\nمرورگر: %s\n\nخودتان بودید؟" % (escape(ch["ip"] or "?"), escape((ch["ua"] or "?")[:80])),
                [[{"text": "✅ بله، من بودم", "callback_data": "wl:ok:%d" % ch["id"]}, {"text": "❌ نه", "callback_data": "wl:no:%d" % ch["id"]}]],
            )
    else:
        s = get_settings()
        # the numeric id is what an owner needs to add this person as a member
        tg.send(chat, "🛡 <b>DowntimeLess</b>\nمانیتور و مدیریت سرورهای VPN\n\nشناسهٔ عددی تلگرام شما: <code>%d</code>\n\nتوسعه‌دهنده: @%s\nGitHub: github.com/%s"
                % (frm["id"], s.dev_telegram, s.dev_github))


def _callback(tg: Telegram, db, cb: Dict[str, Any]) -> None:
    parts = cb.get("data", "").split(":")
    if len(parts) != 3 or parts[0] != "wl":
        return tg.answer(cb["id"])
    ok = auth.decide_challenge(db, int(parts[2]), cb["from"]["id"], parts[1] == "ok")
    tg.answer(cb["id"], "ثبت شد" if ok else "منقضی شده")
    if "message" in cb:
        label = "✅ ورود تأیید شد." if ok and parts[1] == "ok" else ("❌ ورود رد شد." if ok else "⌛ این درخواست منقضی شده است.")
        tg.edit(cb["message"]["chat"]["id"], cb["message"]["message_id"], label)


def notify_admins(tg: Telegram, ws: int, text: str) -> None:
    """A private message to the owner and admins of one workspace; nobody else hears about its fleet."""
    db = connect()
    try:
        rows = db.execute(
            "SELECT u.tg_id FROM workspace_members m JOIN users u ON u.id=m.user_id "
            "WHERE m.workspace_id=? AND m.role IN ('owner','admin') AND u.tg_id IS NOT NULL ORDER BY u.id",
            (ws,),
        ).fetchall()
    finally:
        db.close()
    for r in rows:
        tg.send(r["tg_id"], text)


def poll_forever(tg: Telegram, stop: threading.Event) -> None:
    offset = 0
    while not stop.is_set():
        try:
            for u in tg.updates(offset):
                offset = u["update_id"] + 1
                try:
                    handle(tg, u)
                except Exception:
                    log.exception("update failed")
        except Exception as exc:
            log.warning("polling error: %s", exc)
            stop.wait(5)
