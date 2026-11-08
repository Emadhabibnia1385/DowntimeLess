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


def _renew(**over):
    r = {"certbot_installed": True, "certbot_timer_enabled": True, "certbot_timer_active": True, "certbot_last_run_failed": False}
    r.update(over)
    return r


def test_backup_folders_are_not_certificates(owner):
    sid, key = make_server(owner)
    report(owner, key, ssl={"certs": [cert("a.example.com", 60), cert("sub.example.com.bak-20261103", 30, "acme.sh")], "renew": _renew()})
    assert [r["name"] for r in owner.get("/api/v1/ssl").json()] == ["a.example.com"]


def test_action_flags_follow_the_tool_that_made_the_certificate(owner):
    sid, key = make_server(owner)
    report(owner, key, ssl={"certs": [cert("a.example.com", 60), cert("b.example.com", 60, "acme.sh")], "renew": _renew(acme_sh_cron=True)})
    rows = {r["name"]: r for r in owner.get("/api/v1/ssl").json()}
    assert (rows["a.example.com"]["can_renew"], rows["a.example.com"]["can_delete"]) == (True, True)
    assert (rows["b.example.com"]["can_renew"], rows["b.example.com"]["can_delete"]) == (False, False)


def test_domains_found_by_an_agent_join_the_list_once(owner, monkeypatch):
    monkeypatch.setattr(ssl_svc, "is_public_host", lambda h: True)
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: {"not_after": int(time.time()) + 50 * DAY, "issuer": "LE", "error": None})
    sid, key = make_server(owner, "web", "panel")
    body = {"certs": [], "renew": _renew(), "domains": ["App.Example.com", "app.example.com", "localhost", "-bad.com", "10.0.0.1", "panel.example.org"]}
    report(owner, key, ssl=body)
    report(owner, key, ssl=body)
    rows = owner.get("/api/v1/ssl").json()
    assert sorted(r["name"] for r in rows) == ["app.example.com", "panel.example.org"]
    assert all(r["auto"] and r["server_name"] == "web" for r in rows)


def test_a_found_domain_with_no_dns_is_not_added(owner, monkeypatch):
    monkeypatch.setattr(ssl_svc, "is_public_host", lambda h: False)
    sid, key = make_server(owner)
    report(owner, key, ssl={"certs": [], "renew": _renew(), "domains": ["gone.example.com"]})
    assert owner.get("/api/v1/ssl").json() == []


def test_removing_a_found_domain_hides_it_for_good_but_a_manual_one_is_deleted(owner, monkeypatch):
    monkeypatch.setattr(ssl_svc, "is_public_host", lambda h: True)
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: {"not_after": int(time.time()) + 50 * DAY, "issuer": None, "error": None})
    sid, key = make_server(owner)
    body = {"certs": [], "renew": _renew(), "domains": ["auto.example.com"]}
    report(owner, key, ssl=body)
    auto_id = owner.get("/api/v1/ssl").json()[0]["id"]
    assert owner.delete("/api/v1/domains/%d" % auto_id).status_code == 204
    report(owner, key, ssl=body)
    assert owner.get("/api/v1/ssl").json() == []
    manual = owner.post("/api/v1/domains", json={"host": "manual.example.com"}).json()["id"]
    assert owner.delete("/api/v1/domains/%d" % manual).status_code == 204
    assert connect().execute("SELECT COUNT(*) FROM domains WHERE host='manual.example.com'").fetchone()[0] == 0


def test_found_domains_that_vanish_from_the_server_are_dropped_after_a_week(owner, monkeypatch):
    monkeypatch.setattr(ssl_svc, "is_public_host", lambda h: True)
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: {"not_after": None, "issuer": None, "error": "x"})
    sid, key = make_server(owner)
    report(owner, key, ssl={"certs": [], "renew": _renew(), "domains": ["old.example.com"]})
    db = connect()
    db.execute("UPDATE domains SET seen_at=?", (int(time.time()) - 8 * DAY,))
    ssl_svc.drop_stale_auto(db)
    assert db.execute("SELECT COUNT(*) FROM domains").fetchone()[0] == 0
    db.close()


def test_a_found_domain_that_does_not_answer_is_a_warning_row_but_not_an_issue(owner, monkeypatch):
    monkeypatch.setattr(ssl_svc, "is_public_host", lambda h: True)
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: {"not_after": None, "issuer": None, "error": "اتصال ممکن نشد"})
    sid, key = make_server(owner)
    report(owner, key, ssl={"certs": [], "renew": _renew(), "domains": ["quiet.example.com"]})
    db = connect()
    ssl_svc.probe_due(db)  # the monitor loop does this within seconds
    db.close()
    assert owner.get("/api/v1/ssl").json()[0]["level"] == "warning"
    assert [i for i in owner.get("/api/v1/issues").json() if i["code"].startswith("ssl")] == []


def test_certificate_jobs_need_a_signed_in_or_full_caller_and_a_safe_name(owner):
    sid, key = make_server(owner)
    jobs = "/api/v1/servers/%d/jobs" % sid
    for bad in ("", "../etc", "-rf", "a b", "a;ls", "x" * 300):
        assert owner.post(jobs, json={"kind": "cert_delete", "args": {"name": bad}}).json()["code"] == "job.args_invalid"
    assert owner.post(jobs, json={"kind": "cert_renew", "args": {"name": "a.example.com"}}).status_code == 201
    assert owner.post(jobs, json={"kind": "cert_delete", "args": {"name": "a.example.com"}}).status_code == 201
    token = owner.post("/api/v1/keys", json={"name": "ai", "scope": "read"}).json()["token"]
    owner.post("/api/v1/auth/logout")
    refused = owner.post(jobs, json={"kind": "cert_renew", "args": {"name": "a.example.com"}}, headers={"Authorization": "Bearer " + token})
    assert refused.status_code == 403
