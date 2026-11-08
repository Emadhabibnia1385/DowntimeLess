from conftest import make_server, report


def _login_with(owner, scope):
    token = owner.post("/api/v1/keys", json={"name": "t", "scope": scope}).json()["token"]
    owner.post("/api/v1/auth/logout")
    return {"Authorization": "Bearer " + token}


def test_a_read_key_only_looks(owner):
    sid, key = make_server(owner)
    report(owner, key)
    h = _login_with(owner, "read")
    snap = owner.get("/api/v1/snapshot", headers=h).json()
    assert snap["servers"][0]["name"] == "de-1" and "agent_hash" not in str(snap) and "enroll" not in str(snap)
    assert owner.get("/api/v1/issues", headers=h).status_code == 200
    assert owner.post("/api/v1/servers", json={"name": "x"}, headers=h).json()["code"] == "auth.forbidden"
    assert owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "ping"}, headers=h).json()["code"] == "auth.forbidden"
    assert owner.get("/api/v1/keys", headers=h).status_code == 403


def test_a_full_key_can_do_everything_the_owner_does(owner):
    sid, key = make_server(owner)
    h = _login_with(owner, "full")
    jobs = "/api/v1/servers/%d/jobs" % sid
    for kind in ("ping", "reboot", "apt_upgrade_safe", "self_update"):
        assert owner.post(jobs, json={"kind": kind, "args": {"target": "127.0.0.1"}}, headers=h).status_code == 201, kind
    assert owner.post(jobs, json={"kind": "cert_renew", "args": {"name": "a.example.com"}}, headers=h).status_code == 201
    assert owner.post("/api/v1/servers", json={"name": "new"}, headers=h).status_code == 201
    assert owner.get("/api/v1/keys", headers=h).status_code == 200
    # but a key never mints or revokes keys: that needs the owner signed in
    assert owner.post("/api/v1/keys", json={"name": "child", "scope": "full"}, headers=h).json()["code"] == "auth.forbidden"
    assert owner.delete("/api/v1/keys/1", headers=h).json()["code"] == "auth.forbidden"


def test_even_a_full_key_cannot_change_a_password_or_open_a_profile(owner):
    h = _login_with(owner, "full")
    assert owner.get("/api/v1/auth/me", headers=h).status_code == 403
    assert owner.put("/api/v1/auth/me/password", json={"username": "emad", "password": "long-enough-1"}, headers=h).status_code == 403


def test_bad_keys_and_unknown_scopes_fail(owner):
    assert owner.post("/api/v1/keys", json={"name": "x", "scope": "operate"}).status_code == 422
    owner.post("/api/v1/auth/logout")
    assert owner.get("/api/v1/issues", headers={"Authorization": "Bearer dl_wrong"}).status_code == 401


def test_diagnostics_and_service_actions_are_for_signed_in_people_and_full_keys_only(owner):
    from conftest import make_server

    sid, _ = make_server(owner)
    read = owner.post("/api/v1/keys", json={"name": "r", "scope": "read"}).json()["token"]
    full = owner.post("/api/v1/keys", json={"name": "f", "scope": "full"}).json()["token"]
    jobs = [("processes", {}), ("journal", {"unit": "nginx", "lines": 50}), ("service_restart", {"unit": "nginx.service"}), ("vacuum_logs", {}), ("dns_check", {"target": "example.com"}), ("http_check", {"url": "https://example.com/"}), ("traceroute", {"target": "1.1.1.1"}), ("ports", {}), ("disk_usage", {})]
    for kind, args in jobs:
        assert owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": kind, "args": args}).status_code == 201, kind
        r = owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": kind, "args": args}, headers={"Authorization": "Bearer " + read}, cookies={})
        assert r.status_code in (401, 403), kind
        r = owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": kind, "args": args}, headers={"Authorization": "Bearer " + full}, cookies={})
        assert r.status_code == 201, kind


def test_job_arguments_are_checked_by_the_master_before_anything_is_queued(owner):
    from conftest import make_server

    sid, _ = make_server(owner)
    bad = [("service_restart", {}), ("service_restart", {"unit": "a b"}), ("service_restart", {"unit": "x;reboot"}),
           ("journal", {"lines": 5}), ("journal", {"unit": "$(id)"}), ("traceroute", {"target": "a b"}),
           ("dns_check", {"target": ""}), ("http_check", {"url": "ftp://x"}), ("http_check", {"url": "javascript:1"})]
    for kind, args in bad:
        r = owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": kind, "args": args})
        assert r.status_code == 422 and r.json()["code"] == "job.args_invalid", (kind, args)
