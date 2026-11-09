"""Linking a Telegram account to the account signed in on one browser session, and merging two accounts.

Flow: the panel asks for a link (bound to this user AND this session, 10 minutes, a random token stored as a hash); the
person opens the bot's deep link, the bot records which Telegram account sent /start (the token is then spent) and says
plainly what a yes does, a merge included (confirmation 1). After the yes the bot shows a one-time 6 digit code. The
panel shows exactly what will happen and the person confirms there (confirmation 2) with that code and the fingerprint
of what was shown. The link or merge then happens in one transaction, once.

Trust model: a tap in Telegram can be phished (someone sends their own link to a victim), so the tap alone moves
nothing. The code is shown only to the Telegram account, with a warning never to pass it on, and five wrong codes end
the link. The session that confirms always stays the same account: the Telegram account of the panel owner is never
linked or merged from another account (the owner sets a username and password on their own account instead).

Merge is one way: the absorbed account's memberships, owned workspaces, API keys and credentials move to the survivor
and the absorbed account is deleted. The survivor is always the account signed in; the panel owner is never absorbed. A membership never rises above the better of the two roles,
and a moved API key keeps the role its creator had (api_keys.role_cap), so a merge never widens a key's reach."""
import hashlib
import json
import secrets
import sqlite3
import time
from typing import Any, Dict, List, Optional

from ... import invites
from ...errors import DLError
from ...security import digest, new_token, same
from ...workspaces import PANEL_WORKSPACE, ROLE_RANK, panel_owner_id
from ..reports import events as changelog

LINK_TTL = 600
CODE_TRIES = 5
OPEN = ("pending", "seen", "confirmed")


def start(db: sqlite3.Connection, user_id: int, session_id: int, bot: str) -> Dict[str, Any]:
    user = db.execute("SELECT tg_id FROM users WHERE id=?", (user_id,)).fetchone()
    if user["tg_id"] is not None:
        raise DLError("link.already_linked")
    now = int(time.time())
    # one open link per person: an older one can no longer be used
    db.execute("UPDATE link_tokens SET status='denied' WHERE user_id=? AND status IN ('pending','seen','confirmed')", (user_id,))
    token = new_token(24)
    lid = db.execute(
        "INSERT INTO link_tokens (token_hash, user_id, session_id, status, created_at, expires_at) VALUES (?,?,?,'pending',?,?)",
        (digest(token), user_id, session_id, now, now + LINK_TTL),
    ).lastrowid
    return {"link_id": lid, "deep_link": "https://t.me/%s?start=ln_%s" % (bot, token), "expires_in": LINK_TTL}


def account_label(db: sqlite3.Connection, user_id: int) -> str:
    row = db.execute("SELECT username, name FROM users WHERE id=?", (user_id,)).fetchone()
    return (row["username"] or row["name"] or "#%d" % user_id) if row else "?"


def bot_seen(db: sqlite3.Connection, token: str, tg_id: int, tg_username: Optional[str], tg_name: str) -> Optional[sqlite3.Row]:
    """Bot side of /start ln_<token>: the first Telegram account to use a live token takes it; the token is then spent."""
    won = db.execute(
        "UPDATE link_tokens SET status='seen', tg_id=?, tg_username=?, tg_name=? WHERE token_hash=? AND status='pending' AND expires_at>?",
        (tg_id, (tg_username or None), (tg_name or "")[:64], digest(token), int(time.time())),
    ).rowcount
    if not won:
        return None
    return db.execute("SELECT * FROM link_tokens WHERE token_hash=?", (digest(token),)).fetchone()


def new_code() -> str:
    return "%06d" % secrets.randbelow(10 ** 6)


def refusal(db: sqlite3.Connection, row: sqlite3.Row) -> Optional[str]:
    """Why this Telegram account can never be linked to the asking account: 'panel_owner', 'same' or None."""
    other = db.execute("SELECT id FROM users WHERE tg_id=?", (row["tg_id"],)).fetchone()
    if other is None:
        return None
    if other["id"] == row["user_id"]:
        return "same"
    return "panel_owner" if other["id"] == panel_owner_id(db) else None


def deny(db: sqlite3.Connection, link_id: int) -> None:
    db.execute("UPDATE link_tokens SET status='denied' WHERE id=? AND status IN ('pending','seen','confirmed')", (link_id,))


def owner_label(db: sqlite3.Connection, tg_id: int) -> Optional[str]:
    """The account this Telegram id already has here (it would be merged away), or None."""
    row = db.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    return account_label(db, row["id"]) if row else None


def bot_decide(db: sqlite3.Connection, link_id: int, tg_id: int, yes: bool) -> Optional[str]:
    """Confirmation 1, in Telegram, by the same Telegram account that opened the link.

    None when the link is gone; '' after a no; after a yes the one-time code, which only that Telegram account sees."""
    code = new_code() if yes else ""
    won = db.execute(
        "UPDATE link_tokens SET status=?, code_hash=?, code_tries=0 WHERE id=? AND status='seen' AND tg_id=? AND expires_at>?",
        ("confirmed" if yes else "denied", digest(code) if yes else None, link_id, tg_id, int(time.time())),
    ).rowcount
    return code if won else None


def _row(db: sqlite3.Connection, link_id: int, user_id: int, session_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM link_tokens WHERE id=? AND user_id=? AND session_id=?", (link_id, user_id, session_id)).fetchone()
    if not row:
        raise DLError("link.not_found")
    return row


def _memberships(db: sqlite3.Connection, user_id: int) -> List[sqlite3.Row]:
    return db.execute(
        "SELECT m.workspace_id, m.role, w.name, w.owner_user_id FROM workspace_members m JOIN workspaces w ON w.id=m.workspace_id "
        "WHERE m.user_id=? ORDER BY m.workspace_id",
        (user_id,),
    ).fetchall()


def _keys(db: sqlite3.Connection, user_id: int) -> List[sqlite3.Row]:
    return db.execute(  # ws: caller_row - every key the account made, in whichever workspace, moves with it
        "SELECT id, workspace_id, role_cap FROM api_keys WHERE created_by=? ORDER BY id", (user_id,)
    ).fetchall()


def plan(db: sqlite3.Connection, me: int, tg_id: int) -> Optional[Dict[str, Any]]:
    """What a merge with the account that owns this Telegram id would do, or None when no account owns it."""
    other = db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    if other is None:
        return None
    if other["id"] == me:
        raise DLError("link.same_account")
    p1 = panel_owner_id(db)
    if other["id"] == p1:
        raise DLError("link.panel_owner")
    survivor, absorbed = me, other["id"]
    mine = {r["workspace_id"]: r for r in _memberships(db, survivor)}
    rows = []
    for r in _memberships(db, absorbed):
        before = mine[r["workspace_id"]]["role"] if r["workspace_id"] in mine else None
        after = r["role"] if before is None or ROLE_RANK[r["role"]] > ROLE_RANK[before] else before
        rows.append({"workspace_id": r["workspace_id"], "name": r["name"], "role": r["role"], "survivor_role": before,
                     "result_role": after, "owned": r["owner_user_id"] == absorbed})
    keys = _keys(db, absorbed)
    ab = db.execute("SELECT * FROM users WHERE id=?", (absorbed,)).fetchone()
    sv = db.execute("SELECT * FROM users WHERE id=?", (survivor,)).fetchone()
    moves_password = bool(ab["password_hash"]) and not sv["password_hash"]
    shape = {"survivor": survivor, "absorbed": absorbed, "ws": [(x["workspace_id"], x["role"], x["survivor_role"], x["owned"]) for x in rows],
             "keys": [k["id"] for k in keys], "pw": moves_password, "user": ab["username"], "tg": ab["tg_id"], "p1": p1}
    return {
        "survivor": "this",
        "other": {"username": other["username"], "name": other["name"] or "", "has_password": bool(other["password_hash"]),
                  "tg_username": other["tg_username"]},
        "workspaces": rows, "api_keys": len(keys), "moves_password": moves_password,
        "keeps_panel_owner": p1 in (survivor, absorbed) and p1 is not None,
        "fingerprint": hashlib.sha256(json.dumps(shape, sort_keys=True).encode()).hexdigest()[:32],
        "_survivor": survivor, "_absorbed": absorbed,
    }


def public(p: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return None if p is None else {k: v for k, v in p.items() if not k.startswith("_")}


def view(db: sqlite3.Connection, link_id: int, user_id: int, session_id: int) -> Dict[str, Any]:
    row = _row(db, link_id, user_id, session_id)
    status = row["status"]
    if status in OPEN and row["expires_at"] <= time.time():
        status = "expired"
    out: Dict[str, Any] = {"link_id": row["id"], "status": status, "expires_at": row["expires_at"], "telegram": None, "merge": None}
    if row["tg_id"] is not None and status in ("seen", "confirmed"):
        out["telegram"] = {"id": row["tg_id"], "username": row["tg_username"], "name": row["tg_name"]}
        if status == "confirmed":
            out["merge"] = public(plan(db, user_id, row["tg_id"]))
    return out


def cancel(db: sqlite3.Connection, link_id: int, user_id: int, session_id: int) -> None:
    _row(db, link_id, user_id, session_id)
    db.execute("UPDATE link_tokens SET status='denied' WHERE id=? AND status IN ('pending','seen','confirmed')", (link_id,))


def _check_code(db: sqlite3.Connection, link_id: int, user_id: int, session_id: int, code: Optional[str], now: int) -> None:
    """The code the bot showed must come back before anything moves; a wrong one is counted and five end the link."""
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("SELECT * FROM link_tokens WHERE id=? AND user_id=? AND session_id=?", (link_id, user_id, session_id)).fetchone()
        if not row or row["status"] not in OPEN or row["expires_at"] <= now:
            error = "link.not_found"
        elif row["status"] != "confirmed":
            error = "link.not_ready"
        elif row["code_hash"] and code and same(digest(code.strip()), row["code_hash"]):
            error = None
        else:
            tries = row["code_tries"] + 1
            db.execute("UPDATE link_tokens SET code_tries=?, status=CASE WHEN ?>=? THEN 'denied' ELSE status END WHERE id=?",
                       (tries, tries, CODE_TRIES, link_id))
            error = "link.code_wrong"
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    if error:
        raise DLError(error)


def confirm(db: sqlite3.Connection, link_id: int, user_id: int, session_id: int, merge: bool, fingerprint: Optional[str],
            code: Optional[str] = None) -> Dict[str, Any]:
    """Confirmation 2, in the panel: the bot's code, then link, or merge then link, in one transaction that only one
    request can win. The survivor is always `user_id`. Returns {"user_id": survivor, "merged": bool, "claimed": [...]}."""
    now = int(time.time())
    _check_code(db, link_id, user_id, session_id, code, now)
    db.execute("BEGIN IMMEDIATE")
    try:
        won = db.execute(
            "UPDATE link_tokens SET status='done', done_at=? WHERE id=? AND user_id=? AND session_id=? AND status='confirmed' AND expires_at>?",
            (now, link_id, user_id, session_id, now),
        ).rowcount
        if not won:
            row = db.execute("SELECT status FROM link_tokens WHERE id=? AND user_id=? AND session_id=?", (link_id, user_id, session_id)).fetchone()
            raise DLError("link.not_ready" if row and row["status"] in ("pending", "seen") else "link.not_found")
        row = db.execute("SELECT * FROM link_tokens WHERE id=?", (link_id,)).fetchone()
        me = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if me["tg_id"] is not None:
            raise DLError("link.already_linked")
        p = plan(db, user_id, row["tg_id"])
        if p is not None and not merge:
            raise DLError("link.merge_required")
        if p is not None and fingerprint != p["fingerprint"]:
            raise DLError("link.preview_changed")
        survivor = user_id
        if p is not None:
            survivor = p["_survivor"]
            _merge(db, survivor, p["_absorbed"], now)
        db.execute(
            "UPDATE users SET tg_id=?, tg_username=?, name=CASE WHEN name='' THEN ? ELSE name END WHERE id=?",
            (row["tg_id"], row["tg_username"], row["tg_name"], survivor),
        )
        claimed = invites.request(db, survivor, row["tg_id"], row["tg_username"], row["tg_name"])
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
    return {"user_id": survivor, "merged": p is not None, "claimed": claimed}


def _merge(db: sqlite3.Connection, survivor: int, absorbed: int, now: int) -> None:
    """Move everything of `absorbed` to `survivor`, then delete `absorbed`. Runs inside the caller's transaction."""
    if absorbed == panel_owner_id(db):
        raise DLError("link.preview_changed")  # unreachable by plan(): the panel owner is always the survivor
    roles_before = {r["workspace_id"]: r["role"] for r in _memberships(db, absorbed)}
    for k in _keys(db, absorbed):
        cap = roles_before.get(k["workspace_id"])
        if cap is None:
            cap = "viewer"  # the creator had already left that workspace: the key could do nothing; keep it minimal
        if k["role_cap"] and ROLE_RANK[k["role_cap"]] < ROLE_RANK[cap]:
            cap = k["role_cap"]
        db.execute("UPDATE api_keys SET created_by=?, role_cap=? WHERE id=? AND workspace_id=?", (survivor, cap, k["id"], k["workspace_id"]))
    for r in _memberships(db, absorbed):
        ws = r["workspace_id"]
        mine = db.execute("SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?", (ws, survivor)).fetchone()
        if mine is None:
            db.execute(
                "INSERT INTO workspace_members (workspace_id, user_id, role, added_by, display_name, created_at) "
                "SELECT workspace_id, ?, role, added_by, display_name, created_at FROM workspace_members WHERE workspace_id=? AND user_id=?",
                (survivor, ws, absorbed),
            )
        elif ROLE_RANK[r["role"]] > ROLE_RANK[mine["role"]]:
            db.execute("UPDATE workspace_members SET role=? WHERE workspace_id=? AND user_id=?", (r["role"], ws, survivor))
        changelog.record(db, ws, "account_merged", "#%d -> #%d" % (absorbed, survivor), None, {"from": absorbed, "to": survivor})
    db.execute("UPDATE workspaces SET owner_user_id=? WHERE owner_user_id=? AND id<>?", (survivor, absorbed, PANEL_WORKSPACE))
    db.execute("DELETE FROM workspace_members WHERE user_id=?", (absorbed,))
    db.execute("UPDATE workspace_members SET added_by=? WHERE added_by=?", (survivor, absorbed))
    db.execute("UPDATE jobs SET created_by=? WHERE created_by=?", (survivor, absorbed))  # ws: caller_row - the account's own jobs
    db.execute("UPDATE check_ignores SET created_by=? WHERE created_by=?", (survivor, absorbed))  # ws: caller_row - its own marks
    db.execute("UPDATE issue_acks SET created_by=? WHERE created_by=?", (survivor, absorbed))  # ws: caller_row - its own acks
    db.execute("UPDATE workspace_invites SET invited_by=? WHERE invited_by=?", (survivor, absorbed))  # ws: caller_row - its invites
    db.execute("UPDATE workspace_invites SET claimed_by=? WHERE claimed_by=?", (survivor, absorbed))  # ws: caller_row - its claims
    db.execute("UPDATE login_challenges SET user_id=NULL, status='denied' WHERE user_id=?", (absorbed,))
    ab = db.execute("SELECT * FROM users WHERE id=?", (absorbed,)).fetchone()
    sv = db.execute("SELECT * FROM users WHERE id=?", (survivor,)).fetchone()
    db.execute("UPDATE users SET tg_id=NULL WHERE id=?", (absorbed,))
    if ab["password_hash"] and not sv["password_hash"]:
        db.execute("UPDATE users SET username=NULL WHERE id=?", (absorbed,))
        db.execute("UPDATE users SET username=?, password_hash=? WHERE id=?", (ab["username"], ab["password_hash"], survivor))
    if sv["last_workspace_id"] is None:
        db.execute("UPDATE users SET last_workspace_id=? WHERE id=?", (ab["last_workspace_id"], survivor))
    db.execute("DELETE FROM sessions WHERE user_id=?", (absorbed,))
    db.execute("DELETE FROM users WHERE id=?", (absorbed,))
