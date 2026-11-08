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


def test_categories_are_free_and_a_server_may_have_none(owner):
    cat = owner.post("/api/v1/categories", json={"name": "نیکسون"})
    assert cat.status_code == 201 and cat.json()["server_count"] == 0
    cid = cat.json()["id"]
    assert owner.post("/api/v1/categories", json={"name": "نیکسون"}).json()["code"] == "category.exists"
    r = owner.post("/api/v1/servers", json={"name": "c", "category_id": cid})
    sid = r.json()["server"]["id"]
    assert r.json()["server"]["category_id"] == cid
    assert owner.post("/api/v1/servers", json={"name": "d"}).json()["server"]["category_id"] is None
    assert owner.get("/api/v1/categories").json()[-1]["server_count"] == 1
    assert owner.patch("/api/v1/servers/%d" % sid, json={"category_id": None}).json()["category_id"] is None
    assert owner.patch("/api/v1/servers/%d" % sid, json={"category_id": cid}).json()["category_id"] == cid
    assert owner.patch("/api/v1/servers/%d" % sid, json={"alias": "x"}).json()["category_id"] == cid
    assert owner.patch("/api/v1/servers/%d" % sid, json={"category_id": 9999}).json()["code"] == "category.not_found"


def test_deleting_a_category_keeps_its_servers(owner):
    cid = owner.post("/api/v1/categories", json={"name": "موقت"}).json()["id"]
    sid = owner.post("/api/v1/servers", json={"name": "k", "category_id": cid}).json()["server"]["id"]
    assert owner.patch("/api/v1/categories/%d" % cid, json={"name": "دائمی"}).json()["name"] == "دائمی"
    assert owner.delete("/api/v1/categories/%d" % cid).status_code == 204
    assert owner.get("/api/v1/servers/%d" % sid).json()["category_id"] is None


def test_latest_carries_cores_and_totals(owner):
    sid, key = make_server(owner)
    report(owner, key, cpu_cores=4)
    latest = owner.get("/api/v1/servers/%d" % sid).json()["latest"]
    assert latest["cpu_cores"] == 4 and latest["ram_total_mb"] == 1000 and latest["ram_used_mb"] == 200
    assert latest["disk_total_gb"] == 100 and latest["disk_used_gb"] == 20


def test_only_iran_relays_measure_and_only_towards_foreign_servers(owner):
    relay, kr = make_server(owner, "iran-1", "relay")
    exit_a, ka = make_server(owner, "de-1", "exit")
    exit_b, kb = make_server(owner, "nl-1", "exit")
    report(owner, ka, public_ip="198.51.100.1")
    report(owner, kb, public_ip="198.51.100.2")
    iran = report(owner, kr, public_ip="203.0.113.9", ping=[
        {"target": "198.51.100.1", "loss_pct": 0, "rtt_ms": 40},
        {"target": "198.51.100.2", "loss_pct": 100, "rtt_ms": None},
    ]).json()
    assert {t["target"] for t in iran["ping_targets"]} == {"198.51.100.1", "198.51.100.2"}
    # a foreign server is given nothing to ping, and its stray results never reach the matrix
    assert report(owner, ka, public_ip="198.51.100.1", ping=[{"target": "198.51.100.2", "loss_pct": 100, "rtt_ms": None},
                                                             {"target": "203.0.113.9", "loss_pct": 100, "rtt_ms": None}]).json()["ping_targets"] == []
    cells = owner.get("/api/v1/ping-matrix").json()
    assert {(c["from_name"], c["to_name"]) for c in cells} == {("iran-1", "de-1"), ("iran-1", "nl-1")}
    # one sample is not a window: no link is called bad yet
    assert [i for i in owner.get("/api/v1/issues").json() if i["code"].startswith("ping:")] == []


def test_old_agents_may_run_self_update_at_read_but_nothing_else(owner):
    sid, key = make_server(owner)
    assert owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "self_update"}).status_code == 201
    res = report(owner, key).json()
    assert [j["kind"] for j in res["jobs"]] == ["self_update"] and res["permission"] == "safe"
    # the stored level is untouched, and a batch with any other kind keeps it
    assert owner.get("/api/v1/servers/%d" % sid).json()["permission"] == "read"
    owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "self_update"})
    owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "ping", "args": {"target": "127.0.0.1"}})
    mixed = report(owner, key).json()
    assert len(mixed["jobs"]) == 2 and mixed["permission"] == "read"
    assert report(owner, key).json()["permission"] == "read"


def _fleet_with_relays(owner, losses):
    """Foreign exit 'nl-1' and one relay per entry of `losses`, each reporting that loss to it."""
    _, kx = make_server(owner, "nl-1", "exit")
    report(owner, kx, public_ip="198.51.100.2")
    for n, loss in enumerate(losses, 1):
        _, kr = make_server(owner, "iran-%d" % n, "relay")
        report(owner, kr, public_ip="203.0.113.%d" % n, ping=[{"target": "198.51.100.2", "loss_pct": loss, "rtt_ms": 90}])


def _ping_issues(owner):
    return [i for i in owner.get("/api/v1/issues").json() if i["code"].startswith("ping:")]


def test_a_link_is_bad_only_when_two_relays_agree(owner, monkeypatch):
    from app.features.overview import service as overview

    monkeypatch.setattr(overview, "PING_MIN_SAMPLES", 1)
    _fleet_with_relays(owner, [100, 100, 0])
    (issue,) = _ping_issues(owner)
    assert issue["severity"] == "critical" and issue["server_name"] == "nl-1"
    assert issue["evidence"]["relays"] == ["iran-1", "iran-2"] and issue["evidence"]["measured_by"] == 3


def test_one_relay_disagreeing_with_the_others_is_an_icmp_artefact(owner, monkeypatch):
    from app.features.overview import service as overview

    monkeypatch.setattr(overview, "PING_MIN_SAMPLES", 1)
    _fleet_with_relays(owner, [40, 0, 0])
    assert _ping_issues(owner) == []


def test_a_single_relay_cannot_confirm_so_the_issue_is_only_info(owner, monkeypatch):
    from app.features.overview import service as overview

    monkeypatch.setattr(overview, "PING_MIN_SAMPLES", 1)
    _fleet_with_relays(owner, [100])
    (issue,) = _ping_issues(owner)
    assert issue["severity"] == "info" and "تأیید نشده" in issue["title"]
