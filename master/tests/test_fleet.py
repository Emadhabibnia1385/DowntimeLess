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


def test_a_signed_in_human_may_queue_any_job_on_any_server_and_it_is_delivered_once(owner):
    sid, key = make_server(owner)
    assert owner.get("/api/v1/servers/%d" % sid).json()["permission"] == "full"
    assert owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "reboot"}).status_code == 201
    assert owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "rm -rf"}).json()["code"] == "job.kind_unknown"
    assert [j["kind"] for j in report(owner, key).json()["jobs"]] == ["reboot"]
    assert report(owner, key).json()["jobs"] == []  # delivered once


def test_concurrent_requests_do_not_trip_sqlite_thread_check(owner):
    from concurrent.futures import ThreadPoolExecutor

    sid, key = make_server(owner)
    report(owner, key)
    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(lambda _: owner.get("/api/v1/servers/%d/metrics?range=1h" % sid).status_code, range(40)))
    assert set(codes) == {200}


def test_every_server_tells_its_agent_it_has_full_permission(owner):
    sid, key = make_server(owner)
    assert report(owner, key).json()["permission"] == "full"


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


def test_system_facts_and_extra_levels_reach_the_server_record(owner):
    sid, key = make_server(owner)
    report(owner, key, load1=0.5, load5=0.4, load15=0.3, swap_total_mb=2048, swap_used_mb=512, tcp_established=87,
           info={"os": "Ubuntu 24.04 LTS", "kernel": "6.8.0", "cpu_model": "Xeon", "cpu_cores": 4, "boot_ts": 1790000000, "ipv6": "2001:db8::1"})
    s = owner.get("/api/v1/servers/%d" % sid).json()
    assert s["system"] == {"os": "Ubuntu 24.04 LTS", "kernel": "6.8.0", "cpu_model": "Xeon", "cpu_cores": 4, "boot_ts": 1790000000, "ipv6": "2001:db8::1"}
    assert (s["latest"]["load5"], s["latest"]["swap_pct"], s["latest"]["tcp_established"]) == (0.4, 25.0, 87)


def test_an_old_agent_without_system_facts_gives_empty_ones(owner):
    sid, key = make_server(owner)
    report(owner, key)
    assert owner.get("/api/v1/servers/%d" % sid).json()["system"]["os"] is None


def test_history_carries_load_steal_swap_and_connections_and_serves_six_hours(owner):
    sid, key = make_server(owner)
    report(owner, key, steal_pct=3.0, load1=1.5, swap_total_mb=1000, swap_used_mb=100, tcp_established=40, tcp_retrans_pct=0.5, conntrack_pct=2.0)
    m = owner.get("/api/v1/servers/%d/metrics?range=6h" % sid).json()
    assert m["range"] == "6h"
    p = m["points"][-1]
    assert (p["steal"], p["load1"], p["swap_pct"], p["conns"], p["retrans"], p["conntrack"]) == (3.0, 1.5, 10.0, 40, 0.5, 2.0)


def test_fleet_history_sums_traffic_of_every_server_and_counts_who_reported(owner):
    a, ka = make_server(owner, "a", "exit")
    b, kb = make_server(owner, "b", "exit")
    for key in (ka, kb):
        report(owner, key, net={"iface": "eth0", "rx_bytes": 1000, "tx_bytes": 2000, "rx_bps": 1, "tx_bps": 1})
        report(owner, key, net={"iface": "eth0", "rx_bytes": 1600, "tx_bytes": 2300, "rx_bps": 1, "tx_bps": 1})
    h = owner.get("/api/v1/overview/history?range=1h").json()
    assert (h["rx_total"], h["tx_total"]) == (1200, 600)
    assert h["points"][-1]["servers"] == 2


def test_an_alert_switched_off_is_not_listed_and_comes_back_when_switched_on(owner):
    sid, key = make_server(owner)
    report(owner, key, disk_used_gb=96, failed_units=["x.service"])
    assert {"disk", "failed_units"} <= {i["code"] for i in owner.get("/api/v1/issues").json()}
    got = owner.get("/api/v1/settings").json()
    assert got["on_disk"] == 1 and got["on_offline"] == 1 and got["ssl_warn_days"] == 21
    assert owner.put("/api/v1/settings", json={"on_disk": False, "on_failed_units": 0}).json()["on_disk"] == 0
    assert {"disk", "failed_units"}.isdisjoint(i["code"] for i in owner.get("/api/v1/issues").json())
    owner.put("/api/v1/settings", json={"on_disk": 1, "disk_warn": 99})
    assert "disk" not in {i["code"] for i in owner.get("/api/v1/issues").json()}  # 96 < 99
    owner.put("/api/v1/settings", json={"disk_warn": 80})
    assert "disk" in {i["code"] for i in owner.get("/api/v1/issues").json()}


def test_offline_alert_off_means_no_telegram_message(owner, tg):
    from app.monitor import sweep

    sid, key = make_server(owner)
    report(owner, key)
    db = connect()
    db.execute("UPDATE servers SET last_seen=?", (int(time.time()) - 1000,))
    db.close()
    owner.put("/api/v1/settings", json={"on_offline": 0})
    sweep(tg)
    assert not any("گزارش نمی‌دهد" in m[1] for m in tg.sent)
    owner.put("/api/v1/settings", json={"on_offline": 1})
    sweep(tg)
    assert any("گزارش نمی‌دهد" in m[1] for m in tg.sent)
