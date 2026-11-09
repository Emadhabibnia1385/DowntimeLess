import sqlite3
from typing import List

from fastapi import APIRouter, Depends, Request, Response

from ... import appsettings
from ...db import get_db
from ...deps import COOKIE, Actor, session_any_workspace, session_only
from ...errors import DLError
from ...ratelimit import hit
from ...security import digest
from ...settings import get_settings
from ...workspaces import is_panel_owner, list_for_user, member_role
from . import linking
from . import service as svc
from .schemas import (
    LinkConfirm, LinkDone, LinkStart, LinkView, LoginRequest, PasswordRequest, PollRequest, PollResult, RegisterRequest,
    RegistrationIn, RegistrationOut, StartResult, SwitchWorkspace, UserOut, WebAppRequest, WorkspaceOut,
)

# sign-ups per address and for the whole panel: the second one holds when addresses rotate or a proxy hides them
REGISTER_PER_IP, REGISTER_GLOBAL, REGISTER_WINDOW = 5, 30, 3600

router = APIRouter(prefix="/auth", tags=["auth"])


def _who(request: Request):
    return (request.client.host if request.client else "?"), request.headers.get("user-agent", "")


def same_origin(request: Request) -> None:
    """A browser names the page that sent a request; a state change from another site's page is refused (CSRF).
    Clients that send no Origin (scripts, the test client) are not browsers acting for someone else."""
    origin = request.headers.get("origin")
    if origin is None:
        return
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    if origin.split("://", 1)[-1].rstrip("/") != host:
        raise DLError("auth.origin")


def _cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE, token, max_age=svc.SESSION_TTL, httponly=True, samesite="strict",
        secure=get_settings().cookie_secure, path="/",
    )


@router.post("/telegram/start", response_model=StartResult, operation_id="auth_telegram_start")
def telegram_start(request: Request, db: sqlite3.Connection = Depends(get_db)):
    ip, ua = _who(request)
    hit("start:" + ip, 10, 3600)
    bot = getattr(request.app.state, "bot_username", "")
    if not bot:
        raise DLError("bot.not_configured")
    c = svc.start_challenge(db, ip, ua)
    return {**c, "deep_link": "https://t.me/%s?start=wl_%s" % (bot, c["token"])}


@router.post("/telegram/poll", response_model=PollResult, operation_id="auth_telegram_poll")
def telegram_poll(body: PollRequest, request: Request, response: Response, db: sqlite3.Connection = Depends(get_db)):
    ip, ua = _who(request)
    hit("poll:" + ip, 180, 300)
    status, user, session = svc.poll_challenge(db, body.challenge_id, body.poll_secret, ip, ua)
    if session:
        _cookie(response, session[0])
    return {"status": status, "user": svc.user_out(db, user, session[1]) if user and session else None}


@router.post("/telegram/webapp", response_model=UserOut, operation_id="auth_telegram_webapp")
def telegram_webapp(body: WebAppRequest, request: Request, response: Response, db: sqlite3.Connection = Depends(get_db)):
    ip, ua = _who(request)
    hit("webapp:" + ip, 20, 60)
    info = svc.verify_webapp(body.init_data, get_settings().bot_token) if get_settings().bot_token else None
    if not info:
        raise DLError("auth.webapp_invalid")
    user = svc.registered(db, info.get("id"))
    if not user:
        raise DLError("auth.not_registered")
    token, ws = svc.create_session(db, user["id"], ip, ua)
    _cookie(response, token)
    return svc.user_out(db, user, ws)


@router.post("/login", response_model=UserOut, operation_id="auth_login")
def login(body: LoginRequest, request: Request, response: Response, db: sqlite3.Connection = Depends(get_db)):
    same_origin(request)
    ip, ua = _who(request)
    hit("login:" + ip, 10, 300)
    user = svc.password_login(db, body.username, body.password)
    token, ws = svc.create_session(db, user["id"], ip, ua)
    _cookie(response, token)
    return svc.user_out(db, user, ws)


@router.get("/registration", response_model=RegistrationOut, operation_id="auth_registration")
def registration(db: sqlite3.Connection = Depends(get_db)):
    """Whether the sign-up form is offered on the login page."""
    return {"open": appsettings.registration_open(db)}


@router.put("/registration", response_model=RegistrationOut, operation_id="auth_set_registration")
def set_registration(body: RegistrationIn, request: Request, actor: Actor = Depends(session_any_workspace),
                     db: sqlite3.Connection = Depends(get_db)):
    """Open or close self-registration for the whole panel. Only the panel owner, signed in."""
    same_origin(request)
    if not is_panel_owner(db, actor.user_id):
        raise DLError("auth.forbidden")
    appsettings.put(db, "registration_open", "1" if body.open else "0")
    return {"open": body.open}


@router.post("/register", response_model=UserOut, status_code=201, operation_id="auth_register")
def register(body: RegisterRequest, request: Request, response: Response, db: sqlite3.Connection = Depends(get_db)):
    """A new account (username and password, typed twice) with its own workspace of 20 servers and 30 domains."""
    same_origin(request)
    ip, ua = _who(request)
    hit("register:" + ip, REGISTER_PER_IP, REGISTER_WINDOW)
    hit("register:all", REGISTER_GLOBAL, REGISTER_WINDOW)
    user = svc.register(db, body.username, body.password, body.password2)
    token, ws = svc.create_session(db, user["id"], ip, ua)
    _cookie(response, token)
    return svc.user_out(db, user, ws)


@router.post("/link/start", response_model=LinkStart, operation_id="auth_link_start")
def link_start(request: Request, actor: Actor = Depends(session_any_workspace), db: sqlite3.Connection = Depends(get_db)):
    """A one-time bot link (10 minutes) that ties a Telegram account to me; it works only for this browser session."""
    same_origin(request)
    hit("link:%d" % actor.user_id, 10, 3600)
    bot = getattr(request.app.state, "bot_username", "")
    if not bot:
        raise DLError("bot.not_configured")
    return linking.start(db, actor.user_id, actor.session_id, bot)


@router.get("/link/{link_id}", response_model=LinkView, operation_id="auth_link_view")
def link_view(link_id: int, actor: Actor = Depends(session_any_workspace), db: sqlite3.Connection = Depends(get_db)):
    """Where the link stands; once Telegram said yes, exactly what confirming will do (a merge when the Telegram account
    already has an account here)."""
    hit("linkview:%d" % actor.user_id, 240, 600)
    return linking.view(db, link_id, actor.user_id, actor.session_id)


@router.post("/link/{link_id}/confirm", response_model=LinkDone, operation_id="auth_link_confirm")
def link_confirm(link_id: int, body: LinkConfirm, request: Request, response: Response,
                 actor: Actor = Depends(session_any_workspace), db: sqlite3.Connection = Depends(get_db)):
    """The second confirmation. A merge needs merge=true and the fingerprint shown. The session is renewed afterwards."""
    same_origin(request)
    hit("link:%d" % actor.user_id, 10, 3600)
    done = linking.confirm(db, link_id, actor.user_id, actor.session_id, body.merge, body.fingerprint)
    ip, ua = _who(request)
    db.execute("DELETE FROM sessions WHERE id=?", (actor.session_id,))  # identity changed: a fresh session, never the old token
    token, ws = svc.create_session(db, done["user_id"], ip, ua)
    _cookie(response, token)
    user = db.execute("SELECT * FROM users WHERE id=?", (done["user_id"],)).fetchone()
    tg = getattr(request.app.state, "tg", None)
    if tg is not None and done["claimed"]:
        from ...bot import notify_claims
        notify_claims(tg, db, done["claimed"], user["tg_id"], user["tg_username"] or "", user["name"] or "")
    return {"merged": done["merged"], "claimed_workspaces": sum(1 for c in done["claimed"] if c["added"]), "user": svc.user_out(db, user, ws)}


@router.post("/link/{link_id}/cancel", status_code=204, operation_id="auth_link_cancel")
def link_cancel(link_id: int, request: Request, actor: Actor = Depends(session_any_workspace), db: sqlite3.Connection = Depends(get_db)):
    same_origin(request)
    linking.cancel(db, link_id, actor.user_id, actor.session_id)


@router.post("/logout", status_code=204, operation_id="auth_logout")
def logout(request: Request, response: Response, db: sqlite3.Connection = Depends(get_db)):
    token = request.cookies.get(COOKIE)
    if token:
        db.execute("DELETE FROM sessions WHERE token_hash=?", (digest(token),))
    response.delete_cookie(COOKIE, path="/")


@router.get("/me", response_model=UserOut, operation_id="auth_me")
def me(actor: Actor = Depends(session_only), db: sqlite3.Connection = Depends(get_db)):
    return svc.user_out(db, db.execute("SELECT * FROM users WHERE id=?", (actor.user_id,)).fetchone(), actor.workspace_id)


@router.get("/workspaces", response_model=List[WorkspaceOut], operation_id="auth_workspaces")
def workspaces(actor: Actor = Depends(session_any_workspace), db: sqlite3.Connection = Depends(get_db)):
    """The workspaces I belong to, my own first, with my role in each."""
    return list_for_user(db, actor.user_id)


@router.post("/workspace", response_model=UserOut, operation_id="auth_switch_workspace")
def switch_workspace(body: SwitchWorkspace, actor: Actor = Depends(session_any_workspace), db: sqlite3.Connection = Depends(get_db)):
    """Check that I may act in a workspace and remember it for my next sign-in; any other id is not found.

    The browser tab then names it in X-Workspace-Id on each request. Requests without that header (other tabs of an older
    panel, scripts on the cookie) keep the workspace the session started in, so a switch here never redirects them."""
    hit("switch:%d" % actor.user_id, 60, 60)
    if member_role(db, body.workspace_id, actor.user_id) is None:
        raise DLError("workspace.not_found")
    db.execute("UPDATE users SET last_workspace_id=? WHERE id=?", (body.workspace_id, actor.user_id))
    return svc.user_out(db, db.execute("SELECT * FROM users WHERE id=?", (actor.user_id,)).fetchone(), body.workspace_id)


@router.put("/me/password", response_model=UserOut, operation_id="auth_set_password")
def set_password(body: PasswordRequest, request: Request, actor: Actor = Depends(session_only), db: sqlite3.Connection = Depends(get_db)):
    user = db.execute("SELECT * FROM users WHERE id=?", (actor.user_id,)).fetchone()
    svc.set_password(db, user, body.username, body.password, body.current_password)
    keep = digest(request.cookies.get(COOKIE, ""))
    db.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user["id"], keep))
    return svc.user_out(db, db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone(), actor.workspace_id)
