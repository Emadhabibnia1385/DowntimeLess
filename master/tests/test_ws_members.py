"""Members of a workspace, signing in as an invited person, and the personal workspace everyone gets."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from app import bot
from app.db import connect
from ws_world import invite, login, switch


def _count(sql, *args):
    db = connect()
    try:
        return db.execute(sql, args).fetchone()[0]
    finally:
        db.close()


def test_add_list_change_and_remove_a_member(owner):
    r = owner.post("/api/v1/members", json={"tg_id": 7001, "name": "  Sara  ", "role": "operator"})
    assert r.status_code == 201
    m = r.json()
    assert m["tg_id"] == 7001 and m["name"] == "Sara" and m["role"] == "operator" and m["last_login"] is None and not m["is_me"]
    # the Telegram id was unknown: a user row without password and with no global role was created
    assert _count("SELECT COUNT(*) FROM users WHERE tg_id=7001 AND password_hash IS NULL AND role='none'") == 1
    listed = owner.get("/api/v1/members").json()
    assert [(x["role"], x["is_me"]) for x in listed] == [("owner", True), ("operator", False)]
    assert owner.post("/api/v1/members", json={"tg_id": 7001, "role": "viewer"}).json()["code"] == "member.exists"
    assert owner.patch("/api/v1/members/%d" % m["user_id"], json={"role": "admin"}).json()["role"] == "admin"
    assert owner.delete("/api/v1/members/%d" % m["user_id"]).status_code == 204
    assert owner.delete("/api/v1/members/%d" % m["user_id"]).json()["code"] == "member.not_found"
    assert [x["role"] for x in owner.get("/api/v1/members").json()] == ["owner"]
    kinds = [e["kind"] for e in owner.get("/api/v1/reports/changes").json()["events"]]
    assert kinds[:3] == ["member_removed", "member_role_changed", "member_added"]


def test_member_input_is_validated(owner):
    for role in ("owner", "god", ""):
        assert owner.post("/api/v1/members", json={"tg_id": 7002, "role": role}).json()["code"] == "member.role_invalid", role
    for tg_id in (0, -5, 10 ** 16):
        assert owner.post("/api/v1/members", json={"tg_id": tg_id, "role": "viewer"}).json()["code"] == "member.tg_id_invalid"
    assert owner.post("/api/v1/members", json={"tg_id": "abc", "role": "viewer"}).status_code == 422
    assert owner.post("/api/v1/members", json={"role": "viewer"}).status_code == 422
    assert owner.post("/api/v1/members", json={"tg_id": 7002, "name": "n" * 65, "role": "viewer"}).json()["code"] == "member.name_invalid"
    uid = invite(owner, 7002, "viewer")
    assert owner.patch("/api/v1/members/%d" % uid, json={"role": "owner"}).json()["code"] == "member.role_invalid"
    assert _count("SELECT COUNT(*) FROM workspace_members WHERE workspace_id=1 AND role='owner'") == 1


def test_the_owner_cannot_be_removed_or_changed_not_even_by_themselves(owner):
    me = owner.get("/api/v1/auth/me").json()["id"]
    assert owner.delete("/api/v1/members/%d" % me).json()["code"] == "member.owner_locked"
    assert owner.patch("/api/v1/members/%d" % me, json={"role": "viewer"}).json()["code"] == "member.owner_locked"
    assert owner.delete("/api/v1/members/99999").json()["code"] == "member.not_found"


def test_an_invited_person_signs_in_to_their_own_workspace_once_and_sees_who_invited_them(owner, tg):
    invite(owner, 7003, "admin", "Dina")
    dina = login(owner.app, tg, 7003)
    me = dina.get("/api/v1/auth/me").json()
    # the first sign-in lands in the person's own new workspace, named by Telegram, not by the inviter
    assert me["workspace"]["is_personal"] is True and me["workspace"]["name"] == "فضای کار شخصی" and me["role"] == "owner"
    assert me["is_panel_owner"] is False
    spaces = dina.get("/api/v1/auth/workspaces").json()
    assert [(w["role"], w["is_personal"], w["invited_by"]) for w in spaces] == [("owner", True, None), ("admin", False, "Emad")]
    uid = me["id"]
    login(owner.app, tg, 7003)
    login(owner.app, tg, 7003)
    assert _count("SELECT COUNT(*) FROM workspaces WHERE owner_user_id=?", uid) == 1
    # the owner of workspace 1 already owns it; signing in again never makes them a second workspace
    assert _count("SELECT COUNT(*) FROM workspaces WHERE owner_user_id=(SELECT id FROM users WHERE tg_id=111)") == 1
    # their own workspace starts empty and is theirs to look after, but only the panel owner lets new people in
    assert dina.get("/api/v1/servers").json() == [] and dina.get("/api/v1/members").status_code == 200
    assert dina.post("/api/v1/members", json={"tg_id": 9123, "role": "viewer"}).json()["code"] == "members.panel_owner_only"
    # the next sign-in returns to the workspace used last
    switch(dina, 1)
    again = login(owner.app, tg, 7003)
    assert again.get("/api/v1/auth/me").json()["workspace"]["id"] == 1


def test_a_stranger_is_still_not_registered(client, tg, owner):
    start = client.post("/api/v1/auth/telegram/start").json()
    token = start["deep_link"].split("wl_")[1]
    bot.handle(tg, {"update_id": 1, "message": {"from": {"id": 8888}, "chat": {"id": 8888}, "text": "/start wl_" + token}})
    assert "ثبت نشده" in tg.sent[-1][1]
    r = client.post("/api/v1/auth/telegram/poll", json={"challenge_id": start["challenge_id"], "poll_secret": start["poll_secret"]})
    assert r.json()["status"] == "denied"
    assert _count("SELECT COUNT(*) FROM users WHERE tg_id=8888") == 0


def test_invited_then_removed_before_first_sign_in_is_not_registered(owner, tg):
    uid = invite(owner, 7004, "viewer")
    owner.delete("/api/v1/members/%d" % uid)
    start = owner.post("/api/v1/auth/telegram/start").json()
    bot.handle(tg, {"update_id": 1, "message": {"from": {"id": 7004}, "chat": {"id": 7004}, "text": "/start wl_" + start["deep_link"].split("wl_")[1]}})
    assert "ثبت نشده" in tg.sent[-1][1]


def _init_data(bot_token, user):
    pairs = {"auth_date": str(int(time.time())), "user": json.dumps(user)}
    check = "\n".join("%s=%s" % (k, pairs[k]) for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


def test_mini_app_sign_in_follows_the_same_membership_rule(owner, monkeypatch):
    from app import settings as settings_mod

    monkeypatch.setenv("DL_BOT_TOKEN", "1:test")
    settings_mod._settings = None
    invite(owner, 7005, "viewer", "Mina")
    from fastapi.testclient import TestClient

    c = TestClient(owner.app)
    r = c.post("/api/v1/auth/telegram/webapp", json={"init_data": _init_data("1:test", {"id": 7005})})
    assert r.status_code == 200 and r.json()["workspace"]["is_personal"] is True
    assert c.get("/api/v1/servers", headers={"X-Workspace-Id": "1"}).status_code == 200
    r = c.post("/api/v1/auth/telegram/webapp", json={"init_data": _init_data("1:test", {"id": 7999})})
    assert r.json()["code"] == "auth.not_registered"
    settings_mod._settings = None


def test_removing_a_member_closes_that_workspace_to_their_open_tabs(owner, tg):
    uid = invite(owner, 7006, "admin")
    lea = login(owner.app, tg, 7006)
    switch(lea, 1)
    assert lea.get("/api/v1/servers").status_code == 200
    owner.delete("/api/v1/members/%d" % uid)
    # a tab still naming workspace 1 is refused on every request, never quietly moved
    assert lea.get("/api/v1/servers").json()["code"] == "workspace.not_found"
    assert lea.put("/api/v1/settings", json={"cpu_warn": 1}).json()["code"] == "workspace.not_found"
    assert [w["id"] for w in lea.get("/api/v1/auth/workspaces").json()] != [1]
    del lea.headers["X-Workspace-Id"]
    me = lea.get("/api/v1/auth/me").json()
    assert me["workspace"]["is_personal"] is True and me["role"] == "owner"
    assert lea.post("/api/v1/servers", json={"name": "mine"}).status_code == 201
    assert [s["name"] for s in owner.get("/api/v1/servers").json()] == []  # it went to Lea's workspace, not to A


def test_a_role_change_applies_to_the_next_request(owner, tg):
    uid = invite(owner, 7007, "admin")
    c = login(owner.app, tg, 7007)
    switch(c, 1)
    assert c.post("/api/v1/categories", json={"name": "ok"}).status_code == 201
    owner.patch("/api/v1/members/%d" % uid, json={"role": "viewer"})
    assert c.post("/api/v1/categories", json={"name": "no"}).json()["code"] == "auth.forbidden"


def test_a_key_acts_only_in_the_workspace_it_was_made_in(owner, tg):
    from conftest import make_server

    a_sid, _ = make_server(owner, "alfa-1")
    invite(owner, 7008, "viewer")
    y = login(owner.app, tg, 7008)
    b = next(w["id"] for w in y.get("/api/v1/auth/workspaces").json() if w["is_personal"])
    switch(y, b)
    b_sid, _ = make_server(y, "bravo-1")
    token = y.post("/api/v1/keys", json={"name": "b-full", "scope": "full"}).json()["token"]
    a_key = owner.post("/api/v1/keys", json={"name": "a-read", "scope": "read"}).json()["id"]
    h = {"Authorization": "Bearer " + token}
    from fastapi.testclient import TestClient

    bare = TestClient(owner.app)
    assert [s["name"] for s in bare.get("/api/v1/servers", headers=h).json()] == ["bravo-1"]
    assert bare.get("/api/v1/servers/%d" % a_sid, headers=h).json()["code"] == "server.not_found"
    assert bare.delete("/api/v1/servers/%d" % a_sid, headers=h).json()["code"] == "server.not_found"
    assert bare.delete("/api/v1/keys/%d" % a_key, headers=h).json()["code"] == "auth.forbidden"  # keys never touch keys
    assert y.delete("/api/v1/keys/%d" % a_key).json()["code"] == "key.not_found"
    assert bare.get("/api/v1/servers", headers={**h, "X-Workspace-Id": "1"}).json()["code"] == "workspace.not_found"
    assert bare.post("/api/v1/servers", json={"name": "via-key"}, headers=h).status_code == 201
    assert sorted(s["name"] for s in y.get("/api/v1/servers").json()) == ["bravo-1", "via-key"]
    assert [s["name"] for s in owner.get("/api/v1/servers").json()] == ["alfa-1"]
    assert [k["name"] for k in owner.get("/api/v1/keys").json()] == ["a-read"]
    assert b_sid


def test_a_person_added_without_a_name_takes_the_name_telegram_knows(owner, tg):
    invite(owner, 7009, "viewer")
    start = owner.post("/api/v1/auth/telegram/start").json()
    token = start["deep_link"].split("wl_")[1]
    frm = {"id": 7009, "first_name": "Reza", "last_name": "K", "username": "rezak"}
    bot.handle(tg, {"update_id": 1, "message": {"from": frm, "chat": {"id": 7009}, "text": "/start wl_" + token}})
    row = next(m for m in owner.get("/api/v1/members").json() if m["tg_id"] == 7009)
    assert row["name"] == "" and row["tg_username"] is None  # nothing of their profile shows until they have signed in
    bot.handle(tg, {"update_id": 2, "callback_query": {"id": "x", "from": {"id": 7009}, "data": "wl:ok:%d" % start["challenge_id"]}})
    from fastapi.testclient import TestClient

    c = TestClient(owner.app)
    c.post("/api/v1/auth/telegram/poll", json={"challenge_id": start["challenge_id"], "poll_secret": start["poll_secret"]})
    assert [w["name"] for w in c.get("/api/v1/auth/workspaces").json() if w["is_personal"]] == ["Reza K"]
    row = next(m for m in owner.get("/api/v1/members").json() if m["tg_id"] == 7009)
    assert row["name"] == "Reza K" and row["tg_username"] == "rezak"


def test_start_tells_anyone_their_numeric_id_for_the_owner_to_add(client, tg):
    bot.handle(tg, {"update_id": 1, "message": {"from": {"id": 4242}, "chat": {"id": 4242}, "text": "/start"}})
    assert "<code>4242</code>" in tg.sent[-1][1]
