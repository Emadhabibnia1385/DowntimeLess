import time

from app.db import connect
from conftest import make_server, report


def test_enroll_token_is_single_use(owner):
    r = owner.post("/api/v1/servers", json={"name": "a"})
    token = r.json()["install_command"].split("--token ")[1]
    assert owner.post("/api/agent/v1/enroll", json={"token": token}).status_code == 200
    assert owner.post("/api/agent/v1/enroll", json={"token": token}).json()["code"] == "agent.enroll_invalid"


def test_report_requires_agent_key(owner):
    assert owner.post("/api/agent/v1/report", json={}, headers={"X-Agent-Key": "bad"}).json()["code"] == "agent.invalid"


def test_report_updates_server_and_traffic_deltas_survive_reset(owner):
    sid, key = make_server(owner)
    report(owner, key, public_ip="203.0.113.5", geo={"country": "DE", "city": "Falkenstein", "org": "Hetzner"})
    report(owner, key, net={"rx_bytes": 5000, "tx_bytes": 6000})
    report(owner, key, net={"rx_bytes": 10, "tx_bytes": 20})  # counters reset after a reboot
    s = owner.get("/api/v1/servers/%d" % sid).json()
    assert s["status"] == "online" and s["country"] == "DE" and s["latest"]["ram_pct"] == 20.0
    m = owner.get("/api/v1/servers/%d/metrics?range=1h" % sid).json()
    assert m["rx_total"] == 4000 and m["tx_total"] == 4000


def test_offline_and_issues(owner):
    sid, key = make_server(owner)
    report(owner, key, disk_used_gb=96, tcp_retrans_pct=7.0, failed_units=["x.service"])
    codes = {i["code"] for i in owner.get("/api/v1/issues").json()}
    assert {"disk", "retrans", "failed_units"} <= codes
    db = connect()
    db.execute("UPDATE servers SET last_seen=?", (int(time.time()) - 1000,))
    db.close()
    issues = owner.get("/api/v1/issues").json()
    assert issues[0]["code"] == "offline" and issues[0]["severity"] == "critical"


def test_ping_matrix_and_loss_issue(owner):
    a, ka = make_server(owner, "a", "relay")
    b, kb = make_server(owner, "b", "exit")
    report(owner, kb, public_ip="198.51.100.7")
    res = report(owner, ka, public_ip="203.0.113.9", ping=[{"target": "198.51.100.7", "loss_pct": 100, "rtt_ms": None}]).json()
    assert res["ping_targets"] == [{"target": "198.51.100.7", "tcp_port": None}]
    cell = owner.get("/api/v1/ping-matrix").json()[0]
    assert cell["from_name"] == "a" and cell["to_name"] == "b"
    assert any(i["code"].startswith("ping:") and i["severity"] == "critical" for i in owner.get("/api/v1/issues").json())


def test_mutating_job_needs_permission_and_a_human(owner):
    sid, key = make_server(owner)
    assert owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "reboot"}).json()["code"] == "job.permission"
    owner.patch("/api/v1/servers/%d" % sid, json={"permission": "safe"})
    assert owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "reboot"}).status_code == 201
    assert owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "rm -rf"}).json()["code"] == "job.kind_unknown"
    jobs = report(owner, key).json()["jobs"]
    assert [j["kind"] for j in jobs] == ["reboot"]
    assert report(owner, key).json()["jobs"] == []  # delivered once


def test_concurrent_requests_do_not_trip_sqlite_thread_check(owner):
    from concurrent.futures import ThreadPoolExecutor

    sid, key = make_server(owner)
    report(owner, key)
    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(lambda _: owner.get("/api/v1/servers/%d/metrics?range=1h" % sid).status_code, range(40)))
    assert set(codes) == {200}


def test_self_update_is_allowed_at_read_level_but_other_changes_are_not(owner):
    sid, _ = make_server(owner)
    ok = owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "self_update"})
    assert ok.status_code == 201
    denied = owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "reboot"})
    assert denied.json()["code"] == "job.permission"


def test_agent_outdated_follows_the_served_agent_version(owner):
    sid, key = make_server(owner)
    report(owner, key, agent_version="0.0.1")
    assert owner.get("/api/v1/servers/%d" % sid).json()["agent_outdated"] is True
    from app.features.servers import service

    report(owner, key, agent_version=service.current_agent_version())
    assert owner.get("/api/v1/servers/%d" % sid).json()["agent_outdated"] is False


def test_panel_only_is_a_flag_on_the_panel_role(owner):
    r = owner.post("/api/v1/servers", json={"name": "p", "role": "panel_only"})
    assert r.status_code == 201 and r.json()["server"]["role"] == "panel_only"
    sid = r.json()["server"]["id"]
    assert owner.patch("/api/v1/servers/%d" % sid, json={"role": "panel"}).json()["role"] == "panel"
    assert owner.patch("/api/v1/servers/%d" % sid, json={"role": "panel_only"}).json()["role"] == "panel_only"
    assert owner.patch("/api/v1/servers/%d" % sid, json={"role": "exit"}).json()["role"] == "exit"


def test_only_ipv4_is_kept_as_the_public_ip(owner):
    sid, key = make_server(owner)
    report(owner, key, public_ip="203.0.113.5")
    report(owner, key, public_ip="2a14:4f80:800:4::1")
    assert owner.get("/api/v1/servers/%d" % sid).json()["public_ip"] == "203.0.113.5"
