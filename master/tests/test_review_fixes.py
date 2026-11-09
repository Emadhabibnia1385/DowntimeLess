"""The adversarial review's findings, each as the behaviour that must hold now."""
import time

import pytest
from fastapi.testclient import TestClient

from app.db import connect
from conftest import BOT_ID, add_user, make_server
from ws_world import X_TG, Y_TG, invite, join, login, switch


def _personal(c):
    return [w for w in c.get("/api/v1/auth/workspaces").json() if w["is_personal"]][0]["id"]


def _q(sql, *args):
    db = connect()
    try:
        return db.execute(sql, args).fetchall()
    finally:
        db.close()


# ---- HIGH 1: a workspace joined later never becomes where someone lands ------------------------------------

def test_a_workspace_joined_later_never_hijacks_the_landing(owner, tg):
    invite(owner, Y_TG, "viewer", "Yasmin")
    y = login(owner.app, tg, Y_TG)
    b = _personal(y)
    join(b, X_TG, "admin", added_by=_q("SELECT id FROM users WHERE tg_id=?", Y_TG)[0][0])
    x2 = login(owner.app, tg, X_TG)  # the panel owner signs in again
    me = x2.get("/api/v1/auth/me").json()
    assert me["workspace"]["id"] == 1 and me["role"] == "owner"
    sid = x2.post("/api/v1/servers", json={"name": "real-exit", "role": "exit"}).json()["server"]["id"]
    assert all(s["id"] != sid for s in y.get("/api/v1/servers", headers={"X-Workspace-Id": str(b)}).json())
    # and the switcher says who brought the panel owner into B
    spaces = {w["id"]: w for w in x2.get("/api/v1/auth/workspaces").json()}
    assert spaces[1]["is_personal"] is True and spaces[1]["invited_by"] is None
    assert spaces[b]["is_personal"] is False and spaces[b]["invited_by"] == str(Y_TG)  # Y has no Telegram name in this test


def test_landing_is_remembered_at_every_sign_in_and_falls_back_to_the_own_workspace(owner, tg):
    assert _q("SELECT last_workspace_id FROM users WHERE tg_id=?", X_TG)[0][0] == 1  # set at the fixture's sign-in
    invite(owner, 7101, "admin")
    p = login(owner.app, tg, 7101)
    mine = _personal(p)
    assert p.get("/api/v1/auth/me").json()["workspace"]["id"] == mine
    switch(p, 1)
    assert login(owner.app, tg, 7101).get("/api/v1/auth/me").json()["workspace"]["id"] == 1
    owner.delete("/api/v1/members/%d" % _q("SELECT id FROM users WHERE tg_id=7101")[0][0])
    assert login(owner.app, tg, 7101).get("/api/v1/auth/me").json()["workspace"]["id"] == mine


# ---- HIGH 2: registration stays closed --------------------------------------------------------------------

def test_with_registration_closed_only_the_panel_owner_lets_new_people_in(owner, tg):
    assert owner.put("/api/v1/auth/registration", json={"open": False}).json() == {"open": False}
    invite(owner, Y_TG, "viewer")
    y = login(owner.app, tg, Y_TG)
    switch(y, _personal(y))
    assert y.post("/api/v1/members/invites", json={"tg_username": "@new_person", "role": "viewer"}).json()["code"] == "members.panel_owner_only"
    r = y.post("/api/v1/members", json={"tg_id": 900001, "role": "viewer"})
    assert r.status_code == 403 and r.json()["code"] == "members.panel_owner_only"
    assert _q("SELECT COUNT(*) FROM users WHERE tg_id=900001")[0][0] == 0
    # the chain stops here: the stranger is still not registered
    from app import bot
    start = owner.post("/api/v1/auth/telegram/start").json()
    bot.handle(tg, {"update_id": 9, "message": {"from": {"id": 900001}, "chat": {"id": 900001},
                                                  "text": "/start wl_" + start["deep_link"].split("wl_")[1]}})
    assert "ثبت نشده" in tg.sent[-1][1]
    assert owner.get("/api/v1/auth/me").json()["is_panel_owner"] is True


def test_a_workspace_has_at_most_50_members(owner):
    from app import ratelimit

    for n in range(49):  # the owner is the first
        ratelimit._hits.clear()
        assert owner.post("/api/v1/members", json={"tg_id": 800000 + n, "role": "viewer"}).status_code == 201
    ratelimit._hits.clear()
    assert owner.post("/api/v1/members", json={"tg_id": 801000, "role": "viewer"}).json()["code"] == "members.limit"


def test_signing_in_never_makes_a_second_own_workspace(owner):
    # migration 019 dropped the unique index (a merge may leave two owned workspaces); the insert itself checks
    from app.workspaces import ensure_personal
    db = connect()
    user = db.execute("SELECT * FROM users WHERE id=(SELECT owner_user_id FROM workspaces WHERE id=1)").fetchone()
    first = ensure_personal(db, user)
    assert ensure_personal(db, user) == first == 1
    assert db.execute("SELECT COUNT(*) FROM workspaces WHERE owner_user_id=?", (user["id"],)).fetchone()[0] == 1
    db.close()


# ---- MEDIUM 3: an invite writes no profile and reads none ---------------------------------------------------

def test_an_invite_neither_reads_nor_writes_anyone_s_profile(owner, tg):
    db = connect()
    db.execute("UPDATE users SET tg_username='emad_real' WHERE tg_id=?", (X_TG,))
    db.close()
    invite(owner, Y_TG, "viewer")
    login(owner.app, tg, Y_TG)
    other = owner.post("/api/v1/members", json={"tg_id": 900003, "role": "viewer", "name": "فضای کار اصلی"}).json()
    assert other["name"] == "فضای کار اصلی" and other["tg_username"] is None and other["last_login"] is None
    assert _q("SELECT name FROM users WHERE tg_id=900003")[0][0] == ""  # stays on the membership only
    victim = login(owner.app, tg, 900003)
    assert [w["name"] for w in victim.get("/api/v1/auth/workspaces").json() if w["is_personal"]] == ["فضای کار شخصی"]
    # adding someone who already has a profile answers with the membership only
    db = connect()
    db.execute("UPDATE users SET name='Yasmin Real', tg_username='yreal' WHERE tg_id=?", (Y_TG,))
    db.execute("DELETE FROM workspace_members WHERE workspace_id=1 AND user_id=(SELECT id FROM users WHERE tg_id=?)", (Y_TG,))
    db.close()
    again = owner.post("/api/v1/members", json={"tg_id": Y_TG, "role": "viewer"}).json()
    assert again["name"] == "" and again["tg_username"] is None and again["last_login"] is None


# ---- MEDIUM 4: the shared bot posts only where a workspace has a right to -----------------------------------

def _chan(c, chat):
    return c.post("/api/v1/telegram/channels", json={"name": "c", "chat_id": chat})


def test_a_chat_belongs_to_one_workspace_and_a_private_chat_to_a_manager(owner, tg):
    assert _chan(owner, "-1001111111111").status_code == 201
    person = 7777771  # a Telegram id long enough to be a chat id
    invite(owner, person, "viewer")
    y = login(owner.app, tg, person)
    switch(y, _personal(y))
    taken = _chan(y, "-1001111111111")
    assert taken.status_code == 422 and taken.json()["code"] == "channel.invalid"
    assert _chan(y, "1111111").json()["code"] == "channel.private_not_member"  # someone else's private chat
    assert _chan(y, str(person)).status_code == 201  # their own private chat is fine
    assert _chan(owner, str(person)).json()["code"] == "channel.invalid"  # and it is theirs alone
    sent_to = {c for c, _, _ in tg.sent}
    assert 1111111 not in sent_to and -1001111111111 not in sent_to


def test_a_group_is_saved_only_when_the_bot_may_post_and_a_manager_administers_it(owner, tg):
    tg.admins[-1003000000001] = None  # Telegram refuses: the bot is not in that chat
    tg.admins[-1003000000002] = [{"user": {"id": 555}, "status": "creator"},
                                 {"user": {"id": BOT_ID}, "status": "administrator", "can_post_messages": True}]
    tg.admins[-1003000000003] = [{"user": {"id": X_TG}, "status": "creator"},
                                 {"user": {"id": BOT_ID}, "status": "administrator", "can_post_messages": False}]
    tg.admins[-1003000000004] = [{"user": {"id": X_TG}, "status": "creator"}]
    tg.admins[-1003000000005] = [{"user": {"id": X_TG}, "status": "creator"},
                                 {"user": {"id": BOT_ID}, "status": "administrator", "can_post_messages": True}]
    for chat in (-1003000000001, -1003000000002, -1003000000003, -1003000000004):
        assert _chan(owner, str(chat)).json()["code"] == "channel.not_verified", chat
    assert _chan(owner, "-1003000000005").status_code == 201
    owner.app.state.tg = None
    assert _chan(owner, "-1003000000006").json()["code"] == "bot.not_configured"


def test_the_test_message_and_routes_need_a_verified_channel(owner, tg):
    ch = _chan(owner, "-1004000000001").json()
    db = connect()
    db.execute("UPDATE telegram_channels SET verified_at=NULL WHERE id=?", (ch["id"],))
    db.close()
    assert owner.post("/api/v1/telegram/channels/%d/test" % ch["id"]).json()["code"] == "channel.not_verified"
    assert owner.put("/api/v1/telegram/routes", json={"cpu": "channel:%d" % ch["id"]}).json()["code"] == "route.unknown_channel"


def test_private_alerts_reach_only_the_workspace_s_owner_and_admins(owner, tg):
    from app.bot import notify_admins

    invite(owner, Y_TG, "viewer")
    invite(owner, 7201, "admin")
    login(owner.app, tg, Y_TG)
    tg.sent.clear()
    notify_admins(tg, 1, "x")
    assert sorted(c for c, _, _ in tg.sent) == [X_TG, 7201]


# ---- MEDIUM 5: the workspace travels with each request ------------------------------------------------------

def test_a_second_tab_keeps_writing_where_it_is_looking(owner, tg):
    invite(owner, Y_TG, "viewer")
    y = login(owner.app, tg, Y_TG)
    b = _personal(y)
    join(b, X_TG, "admin")
    tab2 = TestClient(owner.app, cookies=owner.cookies)
    tab2.headers["X-Workspace-Id"] = "1"
    switch(owner, b)  # tab 1 moves to B
    assert tab2.put("/api/v1/settings", json={"cpu_warn": 12}).status_code == 200
    assert [r[0] for r in _q("SELECT workspace_id FROM settings WHERE key='cpu_warn'")] == [1]
    # a request without the header (a script on the cookie) keeps the workspace the session began in
    bare = TestClient(owner.app, cookies=owner.cookies)
    assert bare.get("/api/v1/auth/me").json()["workspace"]["id"] == 1
    assert bare.put("/api/v1/settings", json={"cpu_warn": 13}).status_code == 200  # the reviewer's exact request
    assert [tuple(r) for r in _q("SELECT workspace_id, value FROM settings WHERE key='cpu_warn'")] == [(1, "13.0")]
    for bad in ("abc", "0", "-1", "999", str(b + 1000)):
        r = tab2.get("/api/v1/servers", headers={"X-Workspace-Id": bad})
        assert r.status_code == 404 and r.json()["code"] == "workspace.not_found", bad
    # listing and switching still work from a tab whose workspace is gone
    assert tab2.get("/api/v1/auth/workspaces", headers={"X-Workspace-Id": "999"}).status_code == 200


# ---- LOW 6: keys -----------------------------------------------------------------------------------------

def test_a_full_key_cannot_mint_keys_and_dies_with_its_creator_s_role(owner, tg):
    full = owner.post("/api/v1/keys", json={"name": "ci", "scope": "full"}).json()
    h = {"Authorization": "Bearer " + full["token"]}
    bare = TestClient(owner.app)
    assert bare.post("/api/v1/keys", json={"name": "backdoor", "scope": "full"}, headers=h).json()["code"] == "auth.forbidden"
    assert bare.delete("/api/v1/keys/%d" % full["id"], headers=h).json()["code"] == "auth.forbidden"
    # a key acts no higher than its creator's role in the workspace today
    other = add_user(7301, "admin", "Old owner")
    db = connect()
    db.execute("INSERT INTO api_keys (workspace_id, name, prefix, token_hash, scope, created_by, created_at) "
               "VALUES (1, 'old', 'dl_old', ?, 'full', ?, 1)", (__import__("app.security", fromlist=["digest"]).digest("dl_oldkey"), other))
    db.close()
    sid, _ = make_server(owner, "k-1")
    old = {"Authorization": "Bearer dl_oldkey"}
    assert bare.get("/api/v1/keys", headers=old).json()["code"] == "auth.forbidden"  # admin, not owner
    assert bare.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "reboot"}, headers=old).status_code == 201
    owner.delete("/api/v1/members/%d" % other)
    assert bare.get("/api/v1/servers", headers=old).json()["code"] == "auth.required"  # creator gone: the key is dead


# ---- LOW/MED 7: probing is fair and bounded ---------------------------------------------------------------

def test_one_workspace_s_domain_flood_never_starves_another(owner, monkeypatch):
    from app.features.ssl import service as ssl_svc

    probed = []
    monkeypatch.setattr(ssl_svc, "public_address", lambda h: "198.51.100.9")
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: probed.append(h) or {"not_after": None, "issuer": None, "error": None})
    db = connect()
    now = int(time.time())
    db.execute("INSERT INTO workspaces (id, name, created_at) VALUES (77, 'B', ?)", (now,))
    for i in range(50):
        db.execute("INSERT INTO domains (workspace_id, host, port, created_at) VALUES (77, ?, 443, ?)", ("b%d.example.com" % i, now))
    db.execute("INSERT INTO domains (workspace_id, host, port, created_at, last_checked) VALUES (1, 'a.example.com', 443, ?, ?)",
               (now, now - 7 * 3600))
    ssl_svc.probe_due(db)
    assert "a.example.com" in probed and len(probed) == 5
    # a sweep never spends more than its time budget
    probed.clear()
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: (probed.append(h), time.sleep(0.05))[0] or {"not_after": None, "issuer": None, "error": None})
    ssl_svc.probe_due(db, limit=20, budget_s=0.12)
    assert 1 <= len(probed) <= 4
    db.close()


def test_the_probe_connects_to_the_address_it_checked(monkeypatch):
    from app.features.ssl import service as ssl_svc

    seen = []
    monkeypatch.setattr(ssl_svc.socket, "getaddrinfo", lambda h, p: [(2, 1, 6, "", ("10.0.0.5", 0))])
    monkeypatch.setattr(ssl_svc.socket, "create_connection", lambda addr, timeout: seen.append(addr) or (_ for _ in ()).throw(OSError()))
    assert "آدرس عمومی" in ssl_svc.probe("inside.example.com", 443)["error"] and seen == []
    monkeypatch.setattr(ssl_svc.socket, "getaddrinfo", lambda h, p: [(2, 1, 6, "", ("8.8.8.8", 0))])
    ssl_svc.probe("outside.example.com", 443)
    assert seen == [("8.8.8.8", 443)]


def test_servers_and_domains_have_a_ceiling_per_workspace(owner, monkeypatch):
    from app import workspaces
    from app.features.ssl import service as ssl_svc

    monkeypatch.setattr(workspaces, "MAX_SERVERS", 2)
    make_server(owner, "s1")
    make_server(owner, "s2")
    assert owner.post("/api/v1/servers", json={"name": "s3"}).json()["code"] == "server.limit"
    monkeypatch.setattr(workspaces, "MAX_DOMAINS", 1)
    monkeypatch.setattr(ssl_svc, "is_public_host", lambda h: True)
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: {"not_after": None, "issuer": None, "error": None})
    assert owner.post("/api/v1/domains", json={"host": "one.example.com"}).status_code == 201
    assert owner.post("/api/v1/domains", json={"host": "two.example.com"}).json()["code"] == "domain.limit"
    srv = _q("SELECT * FROM servers WHERE name='s1'")[0]
    db = connect()
    ssl_svc.adopt_domains(db, srv, ["three.example.com"])
    db.close()
    assert _q("SELECT COUNT(*) FROM domains WHERE workspace_id=1")[0][0] == 1


# ---- LOW 9: claiming the panel ----------------------------------------------------------------------------

def test_a_claim_is_refused_cleanly_when_it_cannot_apply(client, tg):
    from app.features.auth import service as auth
    from app.security import digest

    db = connect()
    db.execute("INSERT INTO claims (token_hash, created_at) VALUES (?,?)", (digest("tok"), 1))
    uid = db.execute("INSERT INTO users (tg_id, name, role, created_at) VALUES (55, '', 'none', 1)").lastrowid
    db.execute("INSERT INTO workspaces (name, owner_user_id, created_at) VALUES ('mine', ?, 1)", (uid,))
    assert auth.claim_owner(db, "tok", 55, "x", None) is False  # already owns a workspace
    assert db.execute("SELECT used_at FROM claims").fetchone()[0] is None  # the link is not burnt
    assert db.execute("SELECT owner_user_id FROM workspaces WHERE id=1").fetchone()[0] is None
    assert auth.claim_owner(db, "tok", 66, "Owner", None) is True
    assert auth.claim_owner(db, "tok", 67, "Other", None) is False
    assert db.execute("SELECT u.tg_id FROM workspaces w JOIN users u ON u.id=w.owner_user_id WHERE w.id=1").fetchone()[0] == 66
    db.close()
