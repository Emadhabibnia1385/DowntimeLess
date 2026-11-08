import pytest

from app import alerts
from app.db import connect
from app.features.settings.router import RULES

API = "/api/v1/telegram"


def add_channel(owner, name="کانال هشدار", chat_id="-1001234567890"):
    return owner.post(API + "/channels", json={"name": name, "chat_id": chat_id})


def texts(tg, chat):
    return [m[1] for m in tg.sent if m[0] == chat]


def test_channel_crud_and_validation(owner):
    assert owner.get(API + "/channels").json() == []
    r = add_channel(owner)
    assert r.status_code == 201
    ch = r.json()
    assert ch["name"] == "کانال هشدار" and ch["chat_id"] == "-1001234567890" and ch["id"] > 0
    assert add_channel(owner, "دیگر", "-1001234567890").json()["code"] == "channel.exists"
    assert add_channel(owner, "نام", "@alerts_channel").status_code == 201
    assert add_channel(owner, "لینک", "https://t.me/other_alerts").json()["chat_id"] == "@other_alerts"
    for bad in ("abc", "@a", "-100", "12 34", "@bad name", "https://example.com/x", ""):
        r = add_channel(owner, "x", bad)
        assert r.status_code == 422 and r.json()["code"] == "channel.invalid", bad
    assert add_channel(owner, "   ", "-1005555555").json()["code"] == "channel.invalid"
    assert add_channel(owner, "n" * 65, "-1005555555").json()["code"] == "channel.invalid"
    assert [c["chat_id"] for c in owner.get(API + "/channels").json()] == ["-1001234567890", "@alerts_channel", "@other_alerts"]
    assert owner.delete(API + "/channels/%d" % ch["id"]).status_code == 204
    assert owner.delete(API + "/channels/%d" % ch["id"]).json()["code"] == "channel.not_found"
    assert len(owner.get(API + "/channels").json()) == 2


def test_the_test_endpoint_sends_through_the_bot_and_reports_failures(owner, tg):
    ch = add_channel(owner).json()
    assert owner.post(API + "/channels/%d/test" % ch["id"]).json()["code"] == "bot.not_configured"
    owner.app.state.tg = tg
    assert owner.post(API + "/channels/%d/test" % ch["id"]).status_code == 204
    assert tg.sent[-1][0] == -1001234567890 and "آزمایشی" in tg.sent[-1][1]
    named = add_channel(owner, "نام", "@alerts_channel").json()
    owner.post(API + "/channels/%d/test" % named["id"])
    assert tg.sent[-1][0] == "@alerts_channel"
    tg.refuse = True
    r = owner.post(API + "/channels/%d/test" % ch["id"])
    assert r.status_code == 502 and r.json()["code"] == "telegram.send_failed"
    assert owner.post(API + "/channels/999/test").json()["code"] == "channel.not_found"


def test_nothing_the_api_returns_carries_the_bot_token(owner, tg, monkeypatch):
    secret = "123456:SECRET-TOKEN-VALUE"
    monkeypatch.setenv("DL_BOT_TOKEN", secret)
    from app import settings as settings_mod

    settings_mod._settings = None
    owner.app.state.tg = tg
    ch = add_channel(owner).json()
    bodies = [
        add_channel(owner, "b", "@second_channel").text,
        owner.get(API + "/channels").text,
        owner.post(API + "/channels/%d/test" % ch["id"]).text,
        owner.get(API + "/routes").text,
        owner.put(API + "/routes", json={"cpu": "channel:%d" % ch["id"]}).text,
        owner.get("/api/v1/settings").text,
        owner.get("/api/v1/snapshot").text,
        owner.get("/api/openapi.json").text,
    ]
    assert all(secret not in b and "SECRET-TOKEN" not in b for b in bodies)
    settings_mod._settings = None


def test_routes_default_then_follow_the_choice_and_reject_unknown_input(owner):
    routes = owner.get(API + "/routes").json()
    assert set(routes) == set(RULES)
    for rule in ("offline", "ssl", "conntrack", "ping", "disk", "rebooted", "ip_changed"):
        assert routes[rule] == "admins", rule
    for rule in ("cpu", "ram", "steal", "retrans", "failed_units", "reboot", "resized", "load_per_core"):
        assert routes[rule] == "panel", rule
    ch = add_channel(owner).json()
    cid = "channel:%d" % ch["id"]
    after = owner.put(API + "/routes", json={"cpu": cid, "disk": "panel", "ssl": "admins"}).json()
    assert after["cpu"] == cid and after["disk"] == "panel" and after["ssl"] == "admins"
    assert owner.get(API + "/routes").json()["cpu"] == cid
    assert owner.put(API + "/routes", json={"nonsense": "panel"}).json()["code"] == "route.unknown_rule"
    assert owner.put(API + "/routes", json={"cpu": "channel:9999"}).json()["code"] == "route.unknown_channel"
    assert owner.put(API + "/routes", json={"cpu": "channel:x"}).status_code == 422
    assert owner.put(API + "/routes", json={"cpu": "everyone"}).json()["code"] == "route.invalid"
    # a rejected request changes nothing, not even the valid half of it
    assert owner.put(API + "/routes", json={"ram": cid, "nonsense": "panel"}).status_code == 422
    assert owner.get(API + "/routes").json()["ram"] == "panel"


def test_deleting_a_channel_sends_its_alerts_back_to_their_default(owner):
    ch = add_channel(owner).json()
    owner.put(API + "/routes", json={"disk": "channel:%d" % ch["id"], "cpu": "channel:%d" % ch["id"]})
    owner.delete(API + "/channels/%d" % ch["id"])
    routes = owner.get(API + "/routes").json()
    assert routes["disk"] == "admins" and routes["cpu"] == "panel"


def test_only_admins_and_owners_reach_the_telegram_settings(owner):
    token = owner.post("/api/v1/keys", json={"name": "t", "scope": "read"}).json()["token"]
    h = {"Authorization": "Bearer " + token}
    owner.post("/api/v1/auth/logout")
    for method, path in (("get", "/channels"), ("get", "/routes"), ("post", "/channels/1/test"), ("delete", "/channels/1")):
        assert getattr(owner, method)(API + path, headers=h).status_code == 403
        assert getattr(owner, method)(API + path).status_code == 401
    assert owner.post(API + "/channels", json={"name": "x", "chat_id": "-100123456"}, headers=h).status_code == 403
    assert owner.put(API + "/routes", json={"cpu": "panel"}, headers=h).status_code == 403


def test_notify_resolves_panel_admins_and_channel_routes(owner, tg):
    ch = add_channel(owner).json()
    named = add_channel(owner, "نام", "@alerts_channel").json()
    owner.put(API + "/routes", json={"cpu": "panel", "ram": "admins", "disk": "channel:%d" % ch["id"], "steal": "channel:%d" % named["id"]})
    before = len(tg.sent)
    alerts.notify(tg, 1, "cpu", "x")
    assert len(tg.sent) == before  # panel: nothing is sent
    alerts.notify(tg, 1, "ram", "to admins")
    assert tg.sent[before][:2] == (111, "to admins")
    alerts.notify(tg, 1, "disk", "to channel")
    assert tg.sent[-1][:2] == (-1001234567890, "to channel") and tg.threads[-1] is None
    alerts.notify(tg, 1, "steal", "to username", thread=7)
    assert tg.sent[-1][:2] == ("@alerts_channel", "to username") and tg.threads[-1] == 7
    alerts.notify(tg, 1, "no_such_rule", "ignored")  # an unknown rule is a panel-only one
    assert tg.sent[-1][1] == "to username"


def test_a_failing_send_never_raises_into_the_monitor(owner):
    class Exploding:
        def send(self, *a, **k):
            raise RuntimeError("telegram is down")

    ch = add_channel(owner).json()
    owner.put(API + "/routes", json={"disk": "channel:%d" % ch["id"], "ram": "admins"})
    alerts.notify(Exploding(), 1, "disk", "x")
    alerts.notify(Exploding(), 1, "ram", "x")


def test_a_route_to_a_vanished_channel_falls_back_instead_of_breaking(owner, tg):
    db = connect()
    db.execute("INSERT INTO rule_routes (rule, route) VALUES ('disk', 'channel:77')")
    assert alerts.routes(db, 1)["disk"] == "admins"
    db.close()
    before = len(tg.sent)
    alerts.notify(tg, 1, "disk", "x")
    assert tg.sent[before][0] == 111


def test_rule_of_maps_issue_codes_to_rules():
    cases = {
        "cpu": "cpu", "ram": "ram", "disk": "disk", "steal": "steal", "retrans": "retrans", "conntrack": "conntrack",
        "ping:198.51.100.2": "ping", "ssl_expiry": "ssl", "ssl_auto_renew_off": "ssl", "failed_units": "failed_units",
        "reboot_required": "reboot", "offline": "offline", "rebooted": "rebooted", "ip_changed": "ip_changed",
        "resized": "resized", "blacklisted": "blacklisted", "relay_egress": "relay_egress", "relay_filtered": "relay_filtered",
        "load_per_core": "load_per_core", "quota": "quota", "quota_pair": "quota_pair", "agent_missing": None, "mystery": None,
    }
    for code, rule in cases.items():
        assert alerts.rule_of(code) == rule, code


def test_every_rule_has_a_default_route():
    assert set(alerts.DEFAULT_ROUTES) == set(RULES)
    assert set(alerts.DEFAULT_ROUTES.values()) <= {"panel", "admins"}


@pytest.mark.parametrize("rule", RULES)
def test_every_rule_has_a_switch(owner, rule):
    s = owner.get("/api/v1/settings").json()
    assert s["on_" + rule] == 1
    assert owner.put("/api/v1/settings", json={"on_" + rule: 0}).json()["on_" + rule] == 0
