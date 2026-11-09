"""Self-registration, Telegram linking with merge, and invites by Telegram username.

Threat list (each has tests below, named T1..T11):
T1  username enumeration: login answers the same for an unknown name and a wrong password; sign-up must say "taken",
    so it is held to 5 per address and 30 per hour for the whole panel; adding by account username is owner-only, 30/h.
T2  token reuse: a link token is bound to one account AND one browser session, lives 10 minutes, is taken by the first
    Telegram account that opens it, is confirmed in Telegram only by that account, and completes once.
T3  race on merge: the completing UPDATE is the guard inside one IMMEDIATE transaction; a second confirm loses; a merge
    whose preview changed since it was shown (fingerprint) is refused with nothing changed.
T4  role escalation through merge: a membership ends at the better of the two roles, never above; a moved API key keeps
    the role its creator had (role_cap); the panel owner always survives and keeps workspace 1.
T5  role escalation through invite: a @username invite grants viewer or operator only, never touches an existing
    membership, and only a workspace owner (signed in) makes one.
T6  invite hijack by username squatting: the username comes from Telegram itself, a claim happens once within 14 days,
    and the inviter is told the claimer's numeric id so a squatter is seen and removed.
T7  CSRF: state-changing auth calls from another site's page (Origin) are refused; the cookie stays SameSite=Strict.
T8  session fixation: sign-up and every link or merge hand out a fresh session; the old cookie and the absorbed
    account's sessions stop working.
T9  rate-limit bypass: X-Forwarded-For sent by a client does not reset the per-address bucket, and the global sign-up
    bucket holds when every request comes from a new address.
T10 registration switch: closed means no sign-up and no new people by others than the panel owner; only the panel owner
    flips it.
T11 merge atomicity: a failure in the middle of a merge leaves both accounts exactly as they were.
"""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app import bot
from app.db import connect
from ws_world import invite, login

PW = "correct horse 1"


def q(sql, *args):
    db = connect()
    try:
        return [tuple(r) for r in db.execute(sql, args)]
    finally:
        db.close()


def register(app, username, password=PW, password2=None, **headers):
    c = TestClient(app)
    r = c.post("/api/v1/auth/register", json={"username": username, "password": password, "password2": password2 or password},
               headers=headers)
    return c, r


def tg_start(tg, tg_id, token, username=None, name="Tara"):
    frm = {"id": tg_id, "first_name": name}
    if username:
        frm["username"] = username
    bot.handle(tg, {"update_id": 1, "message": {"from": frm, "chat": {"id": tg_id}, "text": "/start ln_" + token}})


def tg_yes(tg, tg_id, link_id, yes=True):
    bot.handle(tg, {"update_id": 2, "callback_query": {"id": "x", "from": {"id": tg_id}, "data": "ln:%s:%d" % ("ok" if yes else "no", link_id)}})


def start_link(c, tg, tg_id, username=None, yes=True):
    s = c.post("/api/v1/auth/link/start").json()
    token = s["deep_link"].split("start=ln_")[1]
    tg_start(tg, tg_id, token, username)
    if yes:
        tg_yes(tg, tg_id, s["link_id"])
    return s, token


# ---- registration --------------------------------------------------------------------------------------------------

def test_registration_makes_an_account_with_its_own_capped_workspace(owner):
    c, r = register(owner.app, "Sara.k")
    assert r.status_code == 201, r.text
    me = r.json()
    assert me["username"] == "sara.k" and me["role"] == "owner" and me["workspace"]["is_personal"] and me["is_panel_owner"] is False
    assert c.get("/api/v1/auth/me").json()["id"] == me["id"]
    assert q("SELECT server_cap, domain_cap FROM workspaces WHERE owner_user_id=?", me["id"]) == [(20, 30)]
    hashed = q("SELECT password_hash FROM users WHERE id=?", me["id"])[0][0]
    assert hashed.startswith("$argon2") and PW not in hashed
    # the password signs in later
    again = TestClient(owner.app).post("/api/v1/auth/login", json={"username": "sara.k", "password": PW})
    assert again.status_code == 200


@pytest.mark.parametrize("username,pw,pw2,code", [
    ("ab", PW, PW, "register.username_invalid"),
    ("1234567", PW, PW, "register.username_invalid"),  # never reads as a Telegram id where people are added
    ("@sara", PW, PW, "register.username_invalid"),
    ("sara", PW, PW + "x", "register.password_mismatch"),
    ("sara", "short", "short", "register.password_weak"),
    ("sarasara", "sarasara", "sarasara", "register.password_weak"),
])
def test_registration_input_is_validated(owner, username, pw, pw2, code):
    _, r = register(owner.app, username, pw, pw2)
    assert r.json()["code"] == code
    assert q("SELECT COUNT(*) FROM users WHERE username IS NOT NULL") == [(0,)]


def test_registration_caps_apply_to_servers(owner, monkeypatch):
    c, _ = register(owner.app, "capped")
    db = connect()
    db.execute("UPDATE workspaces SET server_cap=1 WHERE owner_user_id=(SELECT id FROM users WHERE username='capped')")
    db.close()
    assert c.post("/api/v1/servers", json={"name": "s1"}).status_code == 201
    assert c.post("/api/v1/servers", json={"name": "s2"}).json()["code"] == "server.limit"


# ---- T1 enumeration -------------------------------------------------------------------------------------------------

def test_t1_login_does_not_tell_unknown_names_from_wrong_passwords(owner):
    register(owner.app, "known")
    c = TestClient(owner.app)
    a = c.post("/api/v1/auth/login", json={"username": "known", "password": "wrong-password"})
    b = c.post("/api/v1/auth/login", json={"username": "nobody", "password": "wrong-password"})
    assert (a.status_code, a.json()) == (b.status_code, b.json())


def test_t1_taken_names_can_only_be_probed_a_few_times_per_address(owner):
    register(owner.app, "taken1")
    c = TestClient(owner.app)
    codes = [c.post("/api/v1/auth/register", json={"username": "taken1", "password": PW, "password2": PW}).json()["code"] for _ in range(6)]
    assert codes[:4] == ["register.username_taken"] * 4 and codes[4:] == ["rate.limited"] * 2


def test_t1_adding_by_account_username_is_for_workspace_owners_only(owner, tg):
    register(owner.app, "hidden.one")
    invite(owner, 7100, "admin")
    admin = login(owner.app, tg, 7100)
    admin.headers["X-Workspace-Id"] = "1"
    assert admin.post("/api/v1/members", json={"who": "hidden.one", "role": "viewer"}).status_code == 403
    assert owner.post("/api/v1/members", json={"who": "nobody.here", "role": "viewer"}).json()["code"] == "member.account_not_found"
    r = owner.post("/api/v1/members", json={"who": "hidden.one", "role": "admin", "name": "H"})
    assert r.status_code == 201 and r.json()["tg_username"] is None and r.json()["name"] == "H"


def test_racing_sign_ups_for_one_name_make_one_account(owner):
    out = []

    def go():
        out.append(register(owner.app, "same.name")[1].status_code)

    threads = [threading.Thread(target=go) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(out).count(201) == 1 and q("SELECT COUNT(*) FROM users WHERE username='same.name'") == [(1,)]
    assert q("SELECT COUNT(*) FROM workspaces WHERE owner_user_id=(SELECT id FROM users WHERE username='same.name')") == [(1,)]


# ---- linking without a merge ----------------------------------------------------------------------------------------

def test_linking_a_new_telegram_account_takes_two_confirmations(owner, tg):
    c, _ = register(owner.app, "linker")
    s, _ = start_link(c, tg, 5001, "linker_tg", yes=False)
    assert c.get("/api/v1/auth/link/%d" % s["link_id"]).json()["status"] == "seen"
    assert c.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={}).json()["code"] == "link.not_ready"
    tg_yes(tg, 5001, s["link_id"])
    view = c.get("/api/v1/auth/link/%d" % s["link_id"]).json()
    assert view["status"] == "confirmed" and view["telegram"]["username"] == "linker_tg" and view["merge"] is None
    r = c.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={})
    assert r.status_code == 200 and r.json()["merged"] is False and r.json()["user"]["tg_username"] == "linker_tg"
    assert q("SELECT tg_id FROM users WHERE username='linker'") == [(5001,)]
    assert c.post("/api/v1/auth/link/start").json()["code"] == "link.already_linked"


def test_a_telegram_no_ends_the_link(owner, tg):
    c, _ = register(owner.app, "nayer")
    s = c.post("/api/v1/auth/link/start").json()
    tg_start(tg, 5002, s["deep_link"].split("ln_")[1])
    tg_yes(tg, 5002, s["link_id"], yes=False)
    assert c.get("/api/v1/auth/link/%d" % s["link_id"]).json()["status"] == "denied"
    assert c.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={}).json()["code"] == "link.not_found"


# ---- T2 token reuse -------------------------------------------------------------------------------------------------

def test_t2_a_token_is_taken_by_the_first_telegram_account_and_only_it_can_say_yes(owner, tg):
    c, _ = register(owner.app, "victim")
    s = c.post("/api/v1/auth/link/start").json()
    token = s["deep_link"].split("ln_")[1]
    tg_start(tg, 6001, token)
    tg_start(tg, 6002, token)  # a second Telegram account replaying the same link
    assert "منقضی شده یا قبلاً استفاده شده" in tg.sent[-1][1]
    tg_yes(tg, 6002, s["link_id"])  # and pressing yes on a link it does not hold
    assert c.get("/api/v1/auth/link/%d" % s["link_id"]).json()["status"] == "seen"
    assert q("SELECT tg_id FROM link_tokens WHERE id=?", s["link_id"]) == [(6001,)]
    assert token not in str(q("SELECT * FROM link_tokens"))  # stored as a hash only


def test_t2_a_link_works_only_in_the_session_that_asked_and_only_once(owner, tg):
    c, _ = register(owner.app, "single")
    s, _ = start_link(c, tg, 6101)
    other = TestClient(owner.app)
    assert other.post("/api/v1/auth/login", json={"username": "single", "password": PW}).status_code == 200
    assert other.get("/api/v1/auth/link/%d" % s["link_id"]).json()["code"] == "link.not_found"
    assert other.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={}).json()["code"] == "link.not_found"
    assert owner.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={}).json()["code"] == "link.not_found"
    assert c.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={}).status_code == 200
    assert c.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={}).status_code in (401, 404)


def test_t2_an_expired_or_replaced_link_is_dead(owner, tg):
    c, _ = register(owner.app, "slow")
    s, token = start_link(c, tg, 6201, yes=False)
    db = connect()
    db.execute("UPDATE link_tokens SET expires_at=? WHERE id=?", (int(time.time()) - 1, s["link_id"]))
    db.close()
    tg_yes(tg, 6201, s["link_id"])
    assert c.get("/api/v1/auth/link/%d" % s["link_id"]).json()["status"] == "expired"
    s2 = c.post("/api/v1/auth/link/start").json()
    s3 = c.post("/api/v1/auth/link/start").json()  # a newer link makes the older one unusable
    tg_start(tg, 6202, s2["deep_link"].split("ln_")[1])
    assert "قبلاً استفاده شده" in tg.sent[-1][1]
    assert c.get("/api/v1/auth/link/%d" % s3["link_id"]).json()["status"] == "pending"


# ---- merge ----------------------------------------------------------------------------------------------------------

def _merge_world(owner, tg):
    """`reg` is a registered account (password, own workspace); Telegram 7300 belongs to account T, a viewer in
    workspace 1 with its own workspace and an API key there."""
    reg, r = register(owner.app, "reg.user")
    invite(owner, 7300, "viewer", "Tee")
    t = login(owner.app, tg, 7300)
    t.headers["X-Workspace-Id"] = str([w for w in t.get("/api/v1/auth/workspaces").json() if w["is_personal"]][0]["id"])
    key = t.post("/api/v1/keys", json={"name": "t-key", "scope": "full"}).json()
    return reg, r.json()["id"], t, key


def test_merge_shows_exactly_what_moves_and_needs_the_fingerprint(owner, tg):
    reg, reg_id, t, key = _merge_world(owner, tg)
    t_id = t.get("/api/v1/auth/me").json()["id"]
    s, _ = start_link(reg, tg, 7300, "tee_tg")
    plan = reg.get("/api/v1/auth/link/%d" % s["link_id"]).json()["merge"]
    assert plan["survivor"] == "this" and plan["api_keys"] == 1 and plan["moves_password"] is False
    assert {(w["workspace_id"], w["role"], w["owned"]) for w in plan["workspaces"]} == {(1, "viewer", False), (int(t.headers["X-Workspace-Id"]), "owner", True)}
    url = "/api/v1/auth/link/%d/confirm" % s["link_id"]
    assert reg.post(url, json={}).json()["code"] == "link.merge_required"
    assert reg.post(url, json={"merge": True, "fingerprint": "0" * 32}).json()["code"] == "link.preview_changed"
    r = reg.post(url, json={"merge": True, "fingerprint": plan["fingerprint"]})
    assert r.status_code == 200 and r.json()["merged"] is True
    assert q("SELECT COUNT(*) FROM users WHERE id=?", t_id) == [(0,)]
    assert q("SELECT tg_id, username FROM users WHERE id=?", reg_id) == [(7300, "reg.user")]
    roles = dict(q("SELECT workspace_id, role FROM workspace_members WHERE user_id=?", reg_id))
    assert roles[1] == "viewer" and roles[int(t.headers["X-Workspace-Id"])] == "owner"
    assert q("SELECT created_by FROM api_keys WHERE id=?", key["id"]) == [(reg_id,)]
    # the key still works, at the role it had
    k = TestClient(owner.app)
    assert k.get("/api/v1/servers", headers={"Authorization": "Bearer " + key["token"]}).status_code == 200
    assert t.get("/api/v1/auth/me").status_code == 401  # the absorbed account's sessions are gone


# ---- T3 race --------------------------------------------------------------------------------------------------------

def test_t3_two_confirmations_at_once_merge_once(owner, tg):
    reg, reg_id, t, _ = _merge_world(owner, tg)
    s, _ = start_link(reg, tg, 7300)
    fp = reg.get("/api/v1/auth/link/%d" % s["link_id"]).json()["merge"]["fingerprint"]
    out = []

    def go():
        out.append(reg.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={"merge": True, "fingerprint": fp}).status_code)

    threads = [threading.Thread(target=go) for _ in range(3)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert out.count(200) == 1
    assert q("SELECT COUNT(*) FROM users WHERE tg_id=7300") == [(1,)]
    assert q("SELECT COUNT(*) FROM workspace_members WHERE user_id=?", reg_id)[0][0] == 3


def test_t3_a_change_after_the_preview_stops_the_merge(owner, tg):
    reg, reg_id, t, _ = _merge_world(owner, tg)
    s, _ = start_link(reg, tg, 7300)
    fp = reg.get("/api/v1/auth/link/%d" % s["link_id"]).json()["merge"]["fingerprint"]
    t.post("/api/v1/keys", json={"name": "late-key", "scope": "read"})  # the other account changed meanwhile
    r = reg.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={"merge": True, "fingerprint": fp})
    assert r.json()["code"] == "link.preview_changed"
    assert q("SELECT COUNT(*) FROM users WHERE tg_id=7300") == [(1,)] and q("SELECT tg_id FROM users WHERE id=?", reg_id) == [(None,)]
    fresh = reg.get("/api/v1/auth/link/%d" % s["link_id"]).json()["merge"]
    assert fresh["api_keys"] == 2 and fresh["fingerprint"] != fp


# ---- T4 escalation through merge ------------------------------------------------------------------------------------

def test_t4_a_moved_key_keeps_the_role_its_creator_had(owner, tg):
    # T is a viewer in workspace 1 with a full key there; reg is made admin of workspace 1 before the merge
    reg, reg_id, t, _ = _merge_world(owner, tg)
    t.headers["X-Workspace-Id"] = "1"
    key = t.post("/api/v1/keys", json={"name": "viewer-key", "scope": "full"})
    assert key.status_code == 403  # a viewer makes no keys at all; give T one directly to model an older key
    db = connect()
    t_id = db.execute("SELECT id FROM users WHERE tg_id=7300").fetchone()["id"]
    from app.security import digest
    db.execute("INSERT INTO api_keys (workspace_id, name, prefix, token_hash, scope, created_by, created_at) VALUES (1,'old','x',?,'full',?,1)",
               (digest("dl_oldtoken"), t_id))
    db.close()
    assert owner.post("/api/v1/members", json={"who": "reg.user", "role": "admin"}).status_code == 201
    s, _ = start_link(reg, tg, 7300)
    plan = reg.get("/api/v1/auth/link/%d" % s["link_id"]).json()["merge"]
    w1 = [w for w in plan["workspaces"] if w["workspace_id"] == 1][0]
    assert (w1["role"], w1["survivor_role"], w1["result_role"]) == ("viewer", "admin", "admin")
    assert reg.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={"merge": True, "fingerprint": plan["fingerprint"]}).status_code == 200
    k = TestClient(owner.app)
    h = {"Authorization": "Bearer dl_oldtoken"}
    assert k.get("/api/v1/servers", headers=h).status_code == 200
    assert k.post("/api/v1/categories", json={"name": "nope"}, headers=h).status_code == 403  # still a viewer's key
    assert q("SELECT role FROM workspace_members WHERE workspace_id=1 AND user_id=?", reg_id) == [("admin",)]


def test_t4_the_panel_owner_always_survives_and_keeps_workspace_1(owner, tg):
    p1 = q("SELECT owner_user_id FROM workspaces WHERE id=1")[0][0]
    reg, r = register(owner.app, "alt.of.owner")
    reg_id = r.json()["id"]
    s, _ = start_link(reg, tg, 111)  # the panel owner's own Telegram account
    plan = reg.get("/api/v1/auth/link/%d" % s["link_id"]).json()["merge"]
    assert plan["survivor"] == "telegram" and plan["keeps_panel_owner"] is True and plan["moves_password"] is True
    done = reg.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={"merge": True, "fingerprint": plan["fingerprint"]})
    assert done.status_code == 200 and done.json()["user"]["id"] == p1 and done.json()["user"]["is_panel_owner"] is True
    assert q("SELECT owner_user_id FROM workspaces WHERE id=1") == [(p1,)]
    assert q("SELECT COUNT(*) FROM users WHERE id=?", reg_id) == [(0,)]
    assert q("SELECT username FROM users WHERE id=?", p1) == [("alt.of.owner",)]
    assert reg.get("/api/v1/auth/me").json()["id"] == p1  # the fresh session belongs to the survivor


# ---- T5 / T6 invites ------------------------------------------------------------------------------------------------

def test_t5_username_invites_never_grant_admin_and_never_change_a_membership(owner, tg):
    assert owner.post("/api/v1/members/invites", json={"tg_username": "@some_admin", "role": "admin"}).json()["code"] == "member.invite_role"
    assert owner.post("/api/v1/members/invites", json={"tg_username": "@ab", "role": "viewer"}).json()["code"] == "member.who_invalid"
    invite(owner, 7400, "admin")
    login(owner.app, tg, 7400)
    db = connect()
    db.execute("UPDATE users SET tg_username='existing_admin' WHERE tg_id=7400")
    db.close()
    assert owner.post("/api/v1/members/invites", json={"tg_username": "Existing_Admin", "role": "viewer"}).status_code == 201
    bot.handle(tg, {"update_id": 3, "message": {"from": {"id": 7400, "username": "Existing_Admin"}, "chat": {"id": 7400}, "text": "/start"}})
    assert q("SELECT role FROM workspace_members WHERE workspace_id=1 AND user_id=(SELECT id FROM users WHERE tg_id=7400)") == [("admin",)]
    assert owner.get("/api/v1/members/invites").json() == []  # spent, without a demotion


def test_t5_only_a_signed_in_workspace_owner_invites(owner, tg):
    invite(owner, 7410, "admin")
    admin = login(owner.app, tg, 7410)
    admin.headers["X-Workspace-Id"] = "1"
    assert admin.post("/api/v1/members/invites", json={"tg_username": "@someone_x", "role": "viewer"}).status_code == 403
    key = owner.post("/api/v1/keys", json={"name": "k", "scope": "full"}).json()["token"]
    k = TestClient(owner.app)
    r = k.post("/api/v1/members/invites", json={"tg_username": "@someone_x", "role": "viewer"}, headers={"Authorization": "Bearer " + key})
    assert r.status_code == 403


def test_t6_a_claim_happens_once_and_the_inviter_sees_who_claimed(owner, tg):
    assert owner.post("/api/v1/members/invites", json={"tg_username": "@new_friend", "role": "operator", "name": "Friend"}).status_code == 201
    bot.handle(tg, {"update_id": 4, "message": {"from": {"id": 7500, "username": "New_Friend", "first_name": "Squat"}, "chat": {"id": 7500}, "text": "/start"}})
    uid = q("SELECT id FROM users WHERE tg_id=7500")[0][0]
    assert q("SELECT role FROM workspace_members WHERE workspace_id=1 AND user_id=?", uid) == [("operator",)]
    note = [t for chat, t, _ in tg.sent if chat == 111][-1]
    assert "<code>7500</code>" in note and "حذف" in note
    # a second account that later takes the same username finds nothing to claim
    bot.handle(tg, {"update_id": 5, "message": {"from": {"id": 7501, "username": "new_friend"}, "chat": {"id": 7501}, "text": "/start"}})
    assert q("SELECT COUNT(*) FROM users WHERE tg_id=7501") == [(0,)]
    # the person can now sign in with Telegram
    assert login(owner.app, tg, 7500).get("/api/v1/auth/me").status_code == 200


def test_t6_an_expired_invite_is_not_claimed_and_a_typed_username_is_not_trusted(owner, tg):
    inv = owner.post("/api/v1/members/invites", json={"tg_username": "late_one", "role": "viewer"}).json()
    db = connect()
    db.execute("UPDATE workspace_invites SET expires_at=? WHERE id=?", (int(time.time()) - 1, inv["id"]))
    db.close()
    bot.handle(tg, {"update_id": 6, "message": {"from": {"id": 7600, "username": "late_one"}, "chat": {"id": 7600}, "text": "/start"}})
    assert q("SELECT COUNT(*) FROM users WHERE tg_id=7600") == [(0,)]
    owner.post("/api/v1/members/invites", json={"tg_username": "real_name", "role": "viewer"})
    # someone without that username who types it into the start text claims nothing
    bot.handle(tg, {"update_id": 7, "message": {"from": {"id": 7601}, "chat": {"id": 7601}, "text": "/start real_name"}})
    assert q("SELECT COUNT(*) FROM users WHERE tg_id=7601") == [(0,)]


def test_linking_claims_the_invites_of_the_linked_username(owner, tg):
    owner.post("/api/v1/members/invites", json={"tg_username": "@reg_tg", "role": "viewer"})
    c, r = register(owner.app, "inv.reg")
    s, _ = start_link(c, tg, 7700, "reg_tg")
    done = c.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={})
    assert done.json()["claimed_workspaces"] == 1
    assert q("SELECT role FROM workspace_members WHERE workspace_id=1 AND user_id=?", r.json()["id"]) == [("viewer",)]


# ---- T7 CSRF --------------------------------------------------------------------------------------------------------

def test_t7_another_site_cannot_drive_sign_up_link_or_the_switch(owner, tg):
    evil = {"Origin": "https://evil.example"}
    _, r = register(owner.app, "csrf.target", **evil)
    assert r.status_code == 403 and r.json()["code"] == "auth.origin"
    assert owner.post("/api/v1/auth/link/start", headers=evil).json()["code"] == "auth.origin"
    assert owner.put("/api/v1/auth/registration", json={"open": False}, headers=evil).json()["code"] == "auth.origin"
    assert TestClient(owner.app).post("/api/v1/auth/login", json={"username": "x", "password": "y"}, headers=evil).json()["code"] == "auth.origin"
    _, ok = register(owner.app, "same.site", Origin="http://testserver")
    assert ok.status_code == 201
    assert "samesite=strict" in ok.headers["set-cookie"].lower() and "httponly" in ok.headers["set-cookie"].lower()


# ---- T8 session fixation --------------------------------------------------------------------------------------------

def test_t8_linking_renews_the_session_and_the_old_cookie_dies(owner, tg):
    c, _ = register(owner.app, "fixed")
    old = c.cookies.get("dl_session")
    s, _ = start_link(c, tg, 7800)
    r = c.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={})
    new = r.cookies.get("dl_session")
    assert new and new != old
    stale = TestClient(owner.app)
    stale.cookies.set("dl_session", old)
    assert stale.get("/api/v1/auth/me").status_code == 401
    assert c.get("/api/v1/auth/me").status_code == 200


def test_t8_sign_up_ignores_a_planted_cookie(owner):
    planted = owner.cookies.get("dl_session")
    c = TestClient(owner.app)
    c.cookies.set("dl_session", planted)
    r = c.post("/api/v1/auth/register", json={"username": "fresh.one", "password": PW, "password2": PW})
    assert r.status_code == 201 and r.cookies.get("dl_session") not in (None, planted)
    assert c.get("/api/v1/auth/me").json()["username"] == "fresh.one"


# ---- T9 rate-limit bypass -------------------------------------------------------------------------------------------

def test_t9_forwarded_for_does_not_reset_the_per_address_bucket(owner):
    c = TestClient(owner.app)
    got = [c.post("/api/v1/auth/register", json={"username": "spoof%d" % n, "password": PW, "password2": PW},
                  headers={"X-Forwarded-For": "10.0.0.%d" % n}).status_code for n in range(6)]
    assert got[:5] == [201] * 5 and got[5] == 429


def test_t9_the_global_bucket_holds_when_every_request_has_a_new_address(owner, monkeypatch):
    from app.features.auth import router as auth_router
    n = {"i": 0}

    def rotating(request):
        n["i"] += 1
        return "198.18.%d.%d" % (n["i"] // 250, n["i"] % 250), "ua"

    monkeypatch.setattr(auth_router, "_who", rotating)
    monkeypatch.setattr(auth_router, "REGISTER_GLOBAL", 3)
    codes = [register(owner.app, "rot%d" % k)[1].status_code for k in range(5)]
    assert codes == [201, 201, 201, 429, 429]


# ---- T10 registration switch ----------------------------------------------------------------------------------------

def test_t10_only_the_panel_owner_closes_registration_and_closed_means_closed(owner, tg):
    assert TestClient(owner.app).get("/api/v1/auth/registration").json() == {"open": True}
    c, _ = register(owner.app, "plain.user")
    assert c.put("/api/v1/auth/registration", json={"open": False}).status_code == 403
    assert TestClient(owner.app).put("/api/v1/auth/registration", json={"open": False}).status_code == 401
    assert owner.put("/api/v1/auth/registration", json={"open": False}).json() == {"open": False}
    _, r = register(owner.app, "too.late")
    assert r.json()["code"] == "register.closed"
    assert c.post("/api/v1/members/invites", json={"tg_username": "@outsider", "role": "viewer"}).json()["code"] == "members.panel_owner_only"
    assert owner.post("/api/v1/members/invites", json={"tg_username": "@outsider", "role": "viewer"}).status_code == 201


# ---- T11 atomicity --------------------------------------------------------------------------------------------------

def test_t11_a_failure_inside_a_merge_changes_nothing(owner, tg, monkeypatch):
    reg, reg_id, t, _ = _merge_world(owner, tg)
    s, _ = start_link(reg, tg, 7300)
    fp = reg.get("/api/v1/auth/link/%d" % s["link_id"]).json()["merge"]["fingerprint"]
    before = q("SELECT * FROM workspace_members ORDER BY workspace_id, user_id"), q("SELECT id, created_by, role_cap FROM api_keys ORDER BY id")
    from app.features.auth import linking
    from app.features.reports import events

    def boom(*a, **k):
        raise RuntimeError("disk full")

    monkeypatch.setattr(linking.changelog, "record", boom)
    with pytest.raises(RuntimeError):
        reg.post("/api/v1/auth/link/%d/confirm" % s["link_id"], json={"merge": True, "fingerprint": fp})
    monkeypatch.setattr(linking.changelog, "record", events.record)
    after = q("SELECT * FROM workspace_members ORDER BY workspace_id, user_id"), q("SELECT id, created_by, role_cap FROM api_keys ORDER BY id")
    assert before == after and q("SELECT status FROM link_tokens WHERE id=?", s["link_id"]) == [("confirmed",)]
    assert q("SELECT COUNT(*) FROM users WHERE tg_id=7300") == [(1,)]

