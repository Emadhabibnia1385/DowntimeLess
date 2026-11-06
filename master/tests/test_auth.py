from app import bot
from conftest import add_user


def test_requires_login(client):
    assert client.get("/api/v1/servers").json()["code"] == "auth.required"


def test_telegram_login_flow_and_single_handover(owner):
    assert owner.get("/api/v1/auth/me").json()["role"] == "owner"


def test_unregistered_telegram_user_is_refused(client, tg):
    start = client.post("/api/v1/auth/telegram/start").json()
    token = start["deep_link"].split("wl_")[1]
    bot.handle(tg, {"update_id": 1, "message": {"from": {"id": 999}, "chat": {"id": 999}, "text": "/start wl_" + token}})
    assert "ثبت نشده" in tg.sent[-1][1]
    r = client.post("/api/v1/auth/telegram/poll", json={"challenge_id": start["challenge_id"], "poll_secret": start["poll_secret"]})
    assert r.json()["status"] == "denied"


def test_wrong_poll_secret_is_not_found(client):
    start = client.post("/api/v1/auth/telegram/start").json()
    r = client.post("/api/v1/auth/telegram/poll", json={"challenge_id": start["challenge_id"], "poll_secret": "nope"})
    assert r.status_code == 404


def test_claim_makes_owner_once(client, tg):
    from app.db import connect
    from app.security import digest
    import time
    db = connect()
    db.execute("INSERT INTO claims (token_hash, created_at) VALUES (?,?)", (digest("tok"), int(time.time())))
    db.close()
    msg = lambda uid: {"update_id": 1, "message": {"from": {"id": uid, "first_name": "A"}, "chat": {"id": uid}, "text": "/start claim_tok"}}  # noqa: E731
    bot.handle(tg, msg(5))
    bot.handle(tg, msg(6))
    db = connect()
    assert [r["tg_id"] for r in db.execute("SELECT tg_id FROM users WHERE role='owner'")] == [5]
    db.close()


def test_password_set_then_login_same_error_for_everything(owner):
    assert owner.put("/api/v1/auth/me/password", json={"username": "emad", "password": "short"}).json()["code"] == "auth.weak_password"
    assert owner.put("/api/v1/auth/me/password", json={"username": "emad", "password": "long-enough-1"}).status_code == 200
    owner.post("/api/v1/auth/logout")
    bad = owner.post("/api/v1/auth/login", json={"username": "emad", "password": "wrong-password"})
    ghost = owner.post("/api/v1/auth/login", json={"username": "nobody", "password": "wrong-password"})
    assert bad.json() == ghost.json() and bad.status_code == 401
    assert owner.post("/api/v1/auth/login", json={"username": "emad", "password": "long-enough-1"}).status_code == 200
