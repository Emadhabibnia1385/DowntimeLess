from conftest import make_server, report


def test_api_key_reads_but_cannot_change_servers(owner):
    sid, key = make_server(owner)
    report(owner, key)
    owner.patch("/api/v1/servers/%d" % sid, json={"permission": "full"})
    token = owner.post("/api/v1/keys", json={"name": "claude", "scope": "operate"}).json()["token"]
    owner.post("/api/v1/auth/logout")
    h = {"Authorization": "Bearer " + token}
    snap = owner.get("/api/v1/snapshot", headers=h).json()
    assert snap["servers"][0]["name"] == "de-1" and "agent_hash" not in str(snap) and "enroll" not in str(snap)
    assert owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "ping"}, headers=h).status_code == 201
    assert owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "reboot"}, headers=h).json()["code"] == "job.permission"
    assert owner.get("/api/v1/keys", headers=h).status_code == 403  # keys never manage keys


def test_read_key_cannot_write_and_bad_key_fails(owner):
    token = owner.post("/api/v1/keys", json={"name": "ro", "scope": "read"}).json()["token"]
    owner.post("/api/v1/auth/logout")
    h = {"Authorization": "Bearer " + token}
    assert owner.get("/api/v1/issues", headers=h).status_code == 200
    assert owner.post("/api/v1/servers", json={"name": "x"}, headers=h).json()["code"] == "auth.forbidden"
    assert owner.get("/api/v1/issues", headers={"Authorization": "Bearer dl_wrong"}).status_code == 401
