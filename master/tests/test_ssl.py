import time

from app.db import connect
from app.features.ssl import service as ssl_svc
from conftest import make_server, report

DAY = 86400


def cert(name, days, source="certbot"):
    return {"name": name, "source": source, "domains": [name], "not_after": int(time.time()) + days * DAY + 100, "days_left": days}


def test_agent_certs_listed_with_levels_and_renewal_state(owner):
    sid, key = make_server(owner, "web", "panel")
    renew = {"certbot_installed": True, "certbot_timer_enabled": True, "certbot_timer_active": True, "certbot_last_run_failed": False}
    report(owner, key, ssl={"certs": [cert("a.example.com", 80), cert("b.example.com", 10), cert("c.example.com", 3)], "renew": renew})
    rows = {r["name"]: r for r in owner.get("/api/v1/ssl").json()}
    assert [rows[n]["level"] for n in ("a.example.com", "b.example.com", "c.example.com")] == ["ok", "warning", "critical"]
    assert rows["a.example.com"]["auto_renew"] == "on" and rows["a.example.com"]["days_left"] == 80
    codes = {(i["code"], i["severity"]) for i in owner.get("/api/v1/issues").json()}
    assert ("ssl_expiry", "warning") in codes and ("ssl_expiry", "critical") in codes


def test_auto_renew_off_and_failed_renewal_are_reported(owner):
    sid, key = make_server(owner)
    renew = {"certbot_installed": True, "certbot_timer_enabled": False, "certbot_timer_active": False, "certbot_last_run_failed": True}
    report(owner, key, ssl={"certs": [cert("x.example.com", 40)], "renew": renew})
    row = owner.get("/api/v1/ssl").json()[0]
    assert row["auto_renew"] == "off" and row["renew_failed"] is True
    codes = {i["code"] for i in owner.get("/api/v1/issues").json()}
    assert {"ssl_auto_renew_off", "ssl_renew_failed"} <= codes


def test_domain_probe_rejects_private_targets_and_stores_result(owner, monkeypatch):
    assert owner.post("/api/v1/domains", json={"host": "localhost"}).json()["code"] == "domain.invalid"
    monkeypatch.setattr(ssl_svc, "is_public_host", lambda h: True)
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: {"not_after": int(time.time()) + 5 * DAY, "issuer": "Let's Encrypt", "error": None})
    r = owner.post("/api/v1/domains", json={"host": "Panel.Example.com"})
    assert r.status_code == 201 and r.json()["name"] == "panel.example.com" and r.json()["level"] == "critical"
    assert owner.post("/api/v1/domains", json={"host": "panel.example.com"}).json()["code"] == "domain.exists"
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: {"not_after": None, "issuer": None, "error": "گواهی معتبر نیست: expired"})
    assert owner.post("/api/v1/domains/%d/check" % r.json()["id"]).json()["error"].startswith("گواهی")
    assert owner.delete("/api/v1/domains/%d" % r.json()["id"]).status_code == 204


def test_alert_sent_once_per_level_change(owner, tg):
    from app import monitor

    sid, key = make_server(owner)
    report(owner, key, ssl={"certs": [cert("x.example.com", 3)], "renew": {"certbot_installed": True}})
    sent = []
    monitor.notify_admins = lambda tgc, text: sent.append(text)
    db = connect()
    monitor._ssl_alerts(db, tg)
    monitor._ssl_alerts(db, tg)
    assert len(sent) == 1 and "x.example.com" in sent[0]
    db.close()


def test_renewal_problems_are_one_issue_per_server_not_one_per_certificate(owner):
    sid, key = make_server(owner)
    renew = {"certbot_installed": True, "certbot_timer_enabled": False, "certbot_timer_active": False, "certbot_last_run_failed": True}
    certs = [cert("a.example.com", 40), cert("b.example.com", 30), cert("c.example.com", 20)]
    report(owner, key, ssl={"certs": certs, "renew": renew})
    codes = [i["code"] for i in owner.get("/api/v1/issues").json()]
    assert codes.count("ssl_renew_failed") == 1 and codes.count("ssl_auto_renew_off") == 1
    off = next(i for i in owner.get("/api/v1/issues").json() if i["code"] == "ssl_auto_renew_off")
    # the 20-day certificate already has its own expiry warning, so only the other two count here
    assert off["evidence"] == {"certs": 2, "days_left": 30}
