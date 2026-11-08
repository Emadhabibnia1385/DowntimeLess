import hashlib
import hmac
import json
import sqlite3
import time
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qsl

from ...errors import DLError
from ...security import check_password, digest, hash_password, new_token, same
from ...workspaces import default_workspace, ensure_personal, is_member_anywhere, workspace_out

CHALLENGE_TTL = 300
SESSION_TTL = 30 * 24 * 3600


def user_out(db: sqlite3.Connection, row: sqlite3.Row, ws: int) -> Dict[str, object]:
    """The person plus the workspace they act in; `role` is their role there, not the legacy users.role."""
    workspace = workspace_out(db, ws, row["id"])
    return {
        "id": row["id"], "name": row["name"], "username": row["username"], "role": workspace["role"],
        "has_password": bool(row["password_hash"]), "tg_username": row["tg_username"], "workspace": workspace,
    }


def create_session(db: sqlite3.Connection, user_id: int, ip: str, ua: str) -> Tuple[str, int]:
    """A new session in the person's default workspace; the first sign-in also creates their own workspace."""
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user or not is_member_anywhere(db, user_id):
        raise DLError("auth.not_registered")
    ensure_personal(db, user)
    ws = default_workspace(db, user_id)
    token = new_token()
    now = int(time.time())
    db.execute(
        "INSERT INTO sessions (user_id, token_hash, ip, ua, created_at, expires_at, active_workspace_id) VALUES (?,?,?,?,?,?,?)",
        (user_id, digest(token), ip, ua[:200], now, now + SESSION_TTL, ws),
    )
    db.execute("UPDATE users SET last_login_at=? WHERE id=?", (now, user_id))
    return token, ws


def start_challenge(db: sqlite3.Connection, ip: str, ua: str) -> Dict[str, object]:
    token, secret, now = new_token(18), new_token(18), int(time.time())
    cur = db.execute(
        "INSERT INTO login_challenges (token_hash, poll_hash, status, ip, ua, created_at, expires_at) VALUES (?,?,?,?,?,?,?)",
        (digest(token), digest(secret), "pending", ip, ua[:200], now, now + CHALLENGE_TTL),
    )
    return {"challenge_id": cur.lastrowid, "token": token, "poll_secret": secret, "expires_in": CHALLENGE_TTL}


def poll_challenge(db: sqlite3.Connection, challenge_id: int, secret: str, ip: str, ua: str):
    row = db.execute("SELECT * FROM login_challenges WHERE id=?", (challenge_id,)).fetchone()
    if not row or not same(row["poll_hash"], digest(secret)):
        raise DLError("auth.challenge_gone")
    if row["expires_at"] < time.time() and row["status"] != "approved":
        return "expired", None, None
    if row["status"] != "approved" or row["consumed_at"]:
        return ("denied" if row["status"] == "denied" else "pending"), None, None
    # hand the session over exactly once
    won = db.execute(
        "UPDATE login_challenges SET consumed_at=? WHERE id=? AND consumed_at IS NULL", (int(time.time()), challenge_id)
    ).rowcount
    if not won:
        return "pending", None, None
    user = db.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
    return "approved", user, create_session(db, user["id"], ip, ua)


def registered(db: sqlite3.Connection, tg_id: int) -> Optional[sqlite3.Row]:
    """A Telegram account may sign in only while it is a member of some workspace; registration stays closed."""
    user = db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
    return user if user and is_member_anywhere(db, user["id"]) else None


def link_challenge(db: sqlite3.Connection, token: str, tg_id: int):
    """Bot side: bind a pending challenge to a registered user. Returns (challenge, user) or None."""
    ch = db.execute(
        "SELECT * FROM login_challenges WHERE token_hash=? AND status='pending' AND expires_at>?",
        (digest(token), int(time.time())),
    ).fetchone()
    if not ch:
        return None
    user = registered(db, tg_id)
    if not user:
        db.execute("UPDATE login_challenges SET status='denied' WHERE id=?", (ch["id"],))
        return ch, None
    db.execute("UPDATE login_challenges SET status='linked', user_id=? WHERE id=?", (user["id"], ch["id"]))
    return ch, user


def decide_challenge(db: sqlite3.Connection, challenge_id: int, tg_id: int, approve: bool) -> bool:
    status = "approved" if approve else "denied"
    return bool(db.execute(
        "UPDATE login_challenges SET status=? WHERE id=? AND status='linked' AND expires_at>? "
        "AND user_id=(SELECT id FROM users WHERE tg_id=?)",
        (status, challenge_id, int(time.time()), tg_id),
    ).rowcount)


def claim_owner(db: sqlite3.Connection, token: str, tg_id: int, name: str, tg_username: Optional[str]) -> bool:
    won = db.execute(
        "UPDATE claims SET used_at=? WHERE token_hash=? AND used_at IS NULL", (int(time.time()), digest(token))
    ).rowcount
    if not won:
        return False
    now = int(time.time())
    db.execute(
        "INSERT INTO users (tg_id, tg_username, name, role, created_at) VALUES (?,?,?,'owner',?) "
        "ON CONFLICT(tg_id) DO UPDATE SET role='owner'",
        (tg_id, tg_username, name, now),
    )
    uid = db.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,)).fetchone()["id"]
    # the claimer owns workspace 1, the panel's original fleet
    db.execute("UPDATE workspaces SET owner_user_id=? WHERE id=1 AND owner_user_id IS NULL", (uid,))
    if db.execute("SELECT 1 FROM workspaces WHERE id=1 AND owner_user_id=?", (uid,)).fetchone():
        db.execute(
            "INSERT INTO workspace_members (workspace_id, user_id, role, added_by, created_at) VALUES (1,?,'owner',?,?) "
            "ON CONFLICT(workspace_id, user_id) DO UPDATE SET role='owner'",
            (uid, uid, now),
        )
    return True


def password_login(db: sqlite3.Connection, username: str, password: str):
    row = db.execute("SELECT * FROM users WHERE username=?", (username.strip().lower(),)).fetchone()
    # same error for unknown user and wrong password
    if not row or not row["password_hash"] or not check_password(row["password_hash"], password):
        raise DLError("auth.invalid")
    if not is_member_anywhere(db, row["id"]):
        raise DLError("auth.invalid")
    return row


def set_password(db: sqlite3.Connection, user: sqlite3.Row, username: Optional[str], password: str, current: Optional[str]) -> None:
    if len(password) < 8:
        raise DLError("auth.weak_password")
    if user["password_hash"] and not (current and check_password(user["password_hash"], current)):
        raise DLError("auth.current_password")
    name = (username or user["username"] or "").strip().lower()
    if len(name) < 3:
        raise DLError("auth.weak_password")
    taken = db.execute("SELECT id FROM users WHERE username=? AND id<>?", (name, user["id"])).fetchone()
    if taken:
        raise DLError("auth.invalid")
    db.execute("UPDATE users SET username=?, password_hash=? WHERE id=?", (name, hash_password(password), user["id"]))


def verify_webapp(init_data: str, bot_token: str, max_age: int = 86400) -> Optional[Dict[str, object]]:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    got = pairs.pop("hash", "")
    check = "\n".join("%s=%s" % (k, pairs[k]) for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    want = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not got or not hmac.compare_digest(got, want):
        return None
    if time.time() - int(pairs.get("auth_date", "0")) > max_age:
        return None
    try:
        return json.loads(pairs["user"])
    except (KeyError, ValueError):
        return None
