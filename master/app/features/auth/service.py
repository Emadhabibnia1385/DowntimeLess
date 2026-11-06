import hashlib
import hmac
import json
import sqlite3
import time
from typing import Dict, Optional
from urllib.parse import parse_qsl

from ...errors import DLError
from ...security import check_password, digest, hash_password, new_token, same

CHALLENGE_TTL = 300
SESSION_TTL = 30 * 24 * 3600


def user_out(row: sqlite3.Row) -> Dict[str, object]:
    return {
        "id": row["id"], "name": row["name"], "username": row["username"], "role": row["role"],
        "has_password": bool(row["password_hash"]), "tg_username": row["tg_username"],
    }


def create_session(db: sqlite3.Connection, user_id: int, ip: str, ua: str) -> str:
    token = new_token()
    now = int(time.time())
    db.execute(
        "INSERT INTO sessions (user_id, token_hash, ip, ua, created_at, expires_at) VALUES (?,?,?,?,?,?)",
        (user_id, digest(token), ip, ua[:200], now, now + SESSION_TTL),
    )
    return token


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


def link_challenge(db: sqlite3.Connection, token: str, tg_id: int):
    """Bot side: bind a pending challenge to a registered user. Returns (challenge, user) or None."""
    ch = db.execute(
        "SELECT * FROM login_challenges WHERE token_hash=? AND status='pending' AND expires_at>?",
        (digest(token), int(time.time())),
    ).fetchone()
    if not ch:
        return None
    user = db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
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
    db.execute(
        "INSERT INTO users (tg_id, tg_username, name, role, created_at) VALUES (?,?,?,'owner',?) "
        "ON CONFLICT(tg_id) DO UPDATE SET role='owner'",
        (tg_id, tg_username, name, int(time.time())),
    )
    return True


def password_login(db: sqlite3.Connection, username: str, password: str):
    row = db.execute("SELECT * FROM users WHERE username=?", (username.strip().lower(),)).fetchone()
    # same error for unknown user and wrong password
    if not row or not row["password_hash"] or not check_password(row["password_hash"], password):
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
