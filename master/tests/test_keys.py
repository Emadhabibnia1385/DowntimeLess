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
    made = owner.post("/api/v1/keys", json={"name": "child", "scope": "read"}, headers=h)
    assert made.status_code == 201 and owner.delete("/api/v1/keys/%d" % made.json()["id"], headers=h).status_code == 204


def test_even_a_full_key_cannot_change_a_password_or_open_a_profile(owner):
    h = _login_with(owner, "full")
    assert owner.get("/api/v1/auth/me", headers=h).status_code == 403
    assert owner.put("/api/v1/auth/me/password", json={"username": "emad", "password": "long-enough-1"}, headers=h).status_code == 403


def test_bad_keys_and_unknown_scopes_fail(owner):
    assert owner.post("/api/v1/keys", json={"name": "x", "scope": "operate"}).status_code == 422
    owner.post("/api/v1/auth/logout")
    assert owner.get("/api/v1/issues", headers={"Authorization": "Bearer dl_wrong"}).status_code == 401
