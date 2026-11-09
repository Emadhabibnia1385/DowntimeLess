"""Real-user path quality per relay and exit, and tunnel health (agent 0.3.3 `paths`, `tunnel_logs`, tunnel bytes)."""
import time

import pytest

from checks_data import checks
from conftest import make_server, report

RELAY_IP = "203.0.113.1"


@pytest.fixture
def clock(monkeypatch):
    now = [float(int(time.time()))]
    real = time.time
    monkeypatch.setattr(time, "time", lambda: now[0])
    yield now
    monkeypatch.setattr(time, "time", real)


def row(peer=RELAY_IP, conns=120, mb=0.01, retrans=5.0, port=21001):
    return {"port": port, "peer": peer, "conns": conns, "mb_per_conn": mb, "rtt_ms": 900.0, "retrans_pct": retrans}


def send(owner, key, clock, step=60, **over):
    clock[0] += step
    body = {"agent_version": "0.3.3", "uptime_s": 100000 + int(clock[0]) % 100000, "public_ip": "198.51.100.2", "checks": checks(**over)}
    r = report(owner, key, **body)
    assert r.status_code == 200, r.text
    return r


def found(owner, prefix):
    return {i["code"]: i for i in owner.get("/api/v1/issues").json() if i["code"].startswith(prefix)}


def fleet(owner):
    _, rk = make_server(owner, "iran-1", "relay")
    report(owner, rk, public_ip=RELAY_IP)
    _, ek = make_server(owner, "nl-1", "exit")
    return ek


def test_low_mb_per_connection_from_one_relay_must_hold_ten_minutes(owner, clock):
    ek = fleet(owner)
    for _ in range(10):
        send(owner, ek, clock, paths=[row(), row(peer="other", mb=0.0)])
    assert found(owner, "path_quality_low") == {}
    send(owner, ek, clock, paths=[row(), row(peer="other", mb=0.0)])
    issue = found(owner, "path_quality_low")["path_quality_low:" + RELAY_IP]
    assert issue["severity"] == "warning" and issue["server_name"] == "nl-1" and issue["evidence"]["relay"] == "iran-1"
    assert issue["evidence"]["mb_per_conn"] == 0.01 and issue["evidence"]["conns"] == 120 and issue["evidence"]["ports"] == ["tcp/21001"]
    assert len(found(owner, "path_quality_low")) == 1  # the users' own bucket is never judged


def test_high_retransmits_count_too_and_good_samples_clear_after_five_minutes(owner, clock):
    ek = fleet(owner)
    for _ in range(12):
        send(owner, ek, clock, paths=[row(mb=2.0, retrans=55.0)])
    assert "path_quality_low:" + RELAY_IP in found(owner, "path_quality_low")
    send(owner, ek, clock, paths=[row(mb=2.0, retrans=3.0)])
    assert found(owner, "path_quality_low")  # one good sample does not clear it
    for _ in range(5):
        send(owner, ek, clock, paths=[row(mb=2.0, retrans=3.0)])
    assert found(owner, "path_quality_low") == {}


def test_few_connections_say_nothing_and_the_switch_hides_it(owner, clock):
    ek = fleet(owner)
    for _ in range(12):
        send(owner, ek, clock, paths=[row(conns=4)])
    assert found(owner, "path_quality_low") == {}
    for _ in range(12):
        send(owner, ek, clock, paths=[row()])
    assert found(owner, "path_quality_low")
    owner.put("/api/v1/settings", json={"on_path_quality_low": 0})
    assert found(owner, "path_quality_low") == {}


def test_health_counts_user_quality_as_measured_once_paths_arrive(owner, clock):
    ek = fleet(owner)
    before = {s["name"]: s for s in owner.get("/api/v1/reports/health").json()["servers"]}
    assert "per_peer_user_quality" in before["iran-1"]["not_measured"]
    send(owner, ek, clock, paths=[row(mb=2.0)])
    after = {s["name"]: s for s in owner.get("/api/v1/reports/health").json()["servers"]}
    assert "per_peer_user_quality" not in after["nl-1"]["not_measured"]
    assert "per_peer_user_quality" not in after["iran-1"]["not_measured"]


def tunnels(rx, tx):
    return {"configs": [{"name": "de1", "type": "backpack", "mode": "client", "transport": "xdi", "ports": [], "peer": "10.77.1.1",
                         "iface": "bp-de1", "unit": "backpack-de1.service", "active": "active", "rx_bytes": rx, "tx_bytes": tx}],
            "links": []}


def test_backpack_handshake_failures_make_an_unhealthy_tunnel(owner, clock):
    _, key = make_server(owner, "nl-1", "exit")
    logs = [{"unit": "backpack-de1.service", "no_answer": 4, "handshake_fail": 3, "wrong_tag": 0}]
    send(owner, key, clock, tunnels=tunnels(10, 10), tunnel_logs=logs)
    issue = found(owner, "tunnel_unhealthy")["tunnel_unhealthy:de1"]
    assert issue["severity"] == "warning" and issue["evidence"]["handshake_fails_10m"] == 7 and issue["evidence"]["iface"] == "bp-de1"
    send(owner, key, clock, tunnels=tunnels(10, 10), tunnel_logs=[dict(logs[0], no_answer=1, handshake_fail=1)])
    assert found(owner, "tunnel_unhealthy") == {}


def test_an_interface_that_only_sends_after_carrying_traffic_is_one_sided(owner, clock):
    _, key = make_server(owner, "nl-1", "exit")
    send(owner, key, clock, tunnels=tunnels(100, 100))
    send(owner, key, clock, tunnels=tunnels(500, 400))  # it carried traffic
    for k in range(16):
        send(owner, key, clock, tunnels=tunnels(500, 500 + k))
    issue = found(owner, "tunnel_unhealthy")["tunnel_unhealthy:de1"]
    assert issue["evidence"]["rx_flat_s"] >= 900
    logs = [{"unit": "backpack-de1.service", "no_answer": 9, "handshake_fail": 0, "wrong_tag": 0}]
    send(owner, key, clock, tunnels=tunnels(500, 600), tunnel_logs=logs)
    assert found(owner, "tunnel_unhealthy")["tunnel_unhealthy:de1"]["severity"] == "critical"


def test_an_idle_tunnel_that_never_moved_or_sends_nothing_is_fine(owner, clock):
    _, key = make_server(owner, "nl-1", "exit")
    for _ in range(20):
        send(owner, key, clock, tunnels=tunnels(100, 100))
    assert found(owner, "tunnel_unhealthy") == {}
