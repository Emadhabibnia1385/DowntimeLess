import logging
import threading
import time
from html import escape
from typing import Any, Dict

from . import invites
from .db import connect
from .features.auth import linking
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


def notify_claims(tg: Telegram, db, claimed, tg_id: int, username: str, name: str) -> None:
    """Tell each inviter who claimed their invite (numeric id and name, so a username squatter is seen), and the person."""
    who = "@%s (شناسهٔ <code>%d</code>%s)" % (escape(username or ""), tg_id, "، " + escape(name) if name else "")
    for c in claimed:
        inviter = db.execute("SELECT tg_id FROM users WHERE id=?", (c["invited_by"],)).fetchone() if c["invited_by"] else None
        if inviter and inviter["tg_id"]:
            tg.send(inviter["tg_id"], "📨 %s دعوت شما به فضای کار «%s» را با نقش %s پذیرفت.\nاگر این همان کسی نیست که دعوت کردید، "
                    "او را از صفحهٔ اعضا حذف کنید." % (who, escape(c["workspace"]), c["role"]))
        if c["added"]:
            tg.send(tg_id, "✅ شما به فضای کار «%s» اضافه شدید. از پنل وارد شوید." % escape(c["workspace"]))


def _claim_invites(tg: Telegram, db, frm: Dict[str, Any]) -> None:
    """Someone invited by @username starts the bot: their account (made now if needed) takes the open invites."""
    username = frm.get("username")
    if not invites.has_open(db, username):
        return
    user = db.execute("SELECT id FROM users WHERE tg_id=?", (frm["id"],)).fetchone()
    uid = user["id"] if user else db.execute(
        "INSERT INTO users (tg_id, tg_username, name, role, created_at) VALUES (?,?,?,'none',?)",
        (frm["id"], username, _name(frm)[:64], int(time.time())),
    ).lastrowid
    notify_claims(tg, db, invites.claim(db, uid, frm["id"], username), frm["id"], username, _name(frm))


LINK_REFUSED = {
    "same": "ℹ️ این تلگرام از قبل به همین حساب وصل است.",
    "panel_owner": "⛔ این تلگرام حساب مالک پنل است و به حساب دیگری وصل یا در آن ادغام نمی‌شود. اگر خودتان مالک هستید، با همین "
                   "تلگرام وارد پنل شوید و در صفحهٔ حساب، نام کاربری و رمز بگذارید. اگر کسی این لینک را برایتان فرستاده، آن را نادیده بگیرید.",
}
LINK_OWN = ("⚠️ فقط اگر <b>خودتان همین الان</b> در پنل «اتصال تلگرام» را زده‌اید «بله» بزنید. اگر کسی این لینک را برایتان فرستاده، "
            "«نه» بزنید.")


def _ask_link(tg: Telegram, db, chat: int, frm: Dict[str, Any], row) -> None:
    """Confirmation 1: say in plain words what a yes does. A phished tap must not look harmless."""
    why = linking.refusal(db, row)
    if why:
        linking.deny(db, row["id"])
        return tg.send(chat, LINK_REFUSED[why])
    account = escape(linking.account_label(db, row["user_id"]))
    mine = linking.owner_label(db, frm["id"])
    if mine is None:
        text = ("🔗 <b>اتصال تلگرام به حساب پنل</b>\nحساب: <code>%s</code>\n\nبعد از اتصال، هر کس به حساب <code>%s</code> دسترسی دارد "
                "می‌تواند با این تلگرام وارد شود و هشدارها و دعوت‌های این تلگرام را بگیرد.\n\n%s\nبعد از «بله» یک کد می‌گیرید که "
                "باید در خود پنل وارد شود." % (account, account, LINK_OWN))
    else:
        text = ("⚠️ <b>ادغام دو حساب</b>\nاین تلگرام الان در پنل حساب «%s» را دارد. با ادامه، حساب «%s» در حساب <code>%s</code> ادغام و "
                "<b>حذف</b> می‌شود: همهٔ فضاهای کار، سرورها و کلیدهای API آن به <code>%s</code> می‌رسد و هر کس رمز آن حساب را "
                "داشته باشد صاحب همه‌شان می‌شود. این کار برگشت ندارد.\n\nفقط اگر هر دو حساب مال خود شماست ادامه دهید.\n%s"
                % (escape(mine), escape(mine), account, account, LINK_OWN))
    tg.send(chat, text, [[{"text": "✅ بله، خودم خواستم", "callback_data": "ln:ok:%d" % row["id"]},
                          {"text": "❌ نه", "callback_data": "ln:no:%d" % row["id"]}]])


def _message(tg: Telegram, db, msg: Dict[str, Any]) -> None:
    frm, chat, text = msg["from"], msg["chat"]["id"], msg["text"].strip()
    arg = text.split(" ", 1)[1].strip() if text.startswith("/start ") else ""
    if text.startswith("/start") and not arg.startswith(("ln_", "claim_")):
        _claim_invites(tg, db, frm)  # a linking account claims its invites when the panel confirms, as itself
    if arg.startswith("ln_"):
        row = linking.bot_seen(db, arg[3:], frm["id"], frm.get("username"), _name(frm))
        if not row:
            tg.send(chat, "⛔ این لینک اتصال پیدا نشد، منقضی شده یا قبلاً استفاده شده است.")
        else:
            _ask_link(tg, db, chat, frm, row)
    elif arg.startswith("claim_"):
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
    if len(parts) == 3 and parts[0] == "ln" and parts[2].isdigit():
        code = linking.bot_decide(db, int(parts[2]), cb["from"]["id"], parts[1] == "ok")
        tg.answer(cb["id"], "ثبت شد" if code is not None else "منقضی شده")
        if "message" in cb:
            if code is None:
                label = "⌛ این درخواست منقضی شده است."
            elif not code:
                label = "❌ اتصال رد شد."
            else:
                label = ("✅ در تلگرام تأیید شد.\n\nکد تأیید: <code>%s</code>\n\nاین کد را فقط <b>خودتان</b> در همان صفحهٔ پنل که باز کرده‌اید "
                         "وارد کنید. آن را برای هیچ‌کس نفرستید؛ مدیر یا پشتیبانی هیچ‌وقت این کد را از شما نمی‌خواهد." % code)
            tg.edit(cb["message"]["chat"]["id"], cb["message"]["message_id"], label)
        return
    if len(parts) != 3 or parts[0] != "wl" or not parts[2].isdigit():
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
