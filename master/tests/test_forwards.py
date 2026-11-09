"""DNAT rules to dead destinations and forwarded ports that other relays cannot get through (agent 0.3.3)."""
import time

import pytest

from app.db import connect
from app.features.overview import service as overview
from conftest import make_server, report

EXIT_IP, RELAY_IP = "198.51.100.2", "203.0.113.1"


@pytest.fixture
def fast(monkeypatch):
    monkeypatch.setattr(overview, "PING_MIN_SAMPLES", 1)


def found(owner, prefix):
    return [i for i in owner.get("/api/v1/issues").json() if i["code"].startswith(prefix)]


def rule(port, to, to_port=None):
    return {"table": "relay_dnat", "proto": "tcp", "port": port, "to": to, "to_port": to_port or port}


def nft(*rules):
    return {"tables": ["ip relay_dnat"], "relay_dnat": True, "dnat_rules": len(rules), "dnat_by_table": {"relay_dnat": len(rules)},
            "dnat": list(rules), "dnat_unparsed": 0, "ip_forward": 1}


def probes(ip, port, fail_pct, error="refused", n=10):
    bad = round(n * fail_pct / 100)
    return [{"target": ip, "port": port, "ok": k >= bad, "rtt_ms": 50 if k >= bad else None,
             "error": None if k >= bad else error, "tls": None} for k in range(n)]


def exit_server(owner, ports=(443,)):
    _, k = make_server(owner, "nl-1", "exit")
    report(owner, k, agent_version="0.3.3", public_ip=EXIT_IP,
           checks={"listeners": [{"proto": "tcp", "port": p, "proc": "xray", "addr": "0.0.0.0"} for p in ports]})
    return k


def relay(owner, name="iran-1", ip=RELAY_IP, rules=(), probe=()):
    sid, k = make_server(owner, name, "relay")
    r = report(owner, k, agent_version="0.3.3", public_ip=ip, checks={"nft": nft(*rules)}, probes=list(probe))
    assert r.status_code == 200, r.text
    return sid, k, r.json()


def prove(ip, port):
    db = connect()
    db.execute("INSERT OR REPLACE INTO probe_ports (workspace_id, target, port, last_ok) VALUES (1,?,?,?)", (ip, port, int(time.time())))
    db.close()


# ---- dnat_dead_target / dnat_unknown_target --------------------------------------------------------

def test_a_rule_to_a_known_server_that_does_not_listen_is_a_warning_and_a_failing_probe_confirms_it(owner, fast):
    exit_server(owner)
    relay(owner, rules=[rule(21001, EXIT_IP)])
    [issue] = found(owner, "dnat_dead_target")
    assert issue["severity"] == "warning" and issue["server_name"] == "iran-1"
    assert issue["evidence"]["rules"] == ["21001 -> 198.51.100.2:21001"] and issue["evidence"]["targets"] == ["nl-1"]
    assert issue["evidence"]["not_listening"] == ["21001 -> 198.51.100.2:21001"] and issue["evidence"]["ports"] == ["tcp/21001"]
    relay(owner, "iran-2", "203.0.113.2", rules=[rule(21001, EXIT_IP)], probe=probes(EXIT_IP, 21001, 100))
    sev = {i["server_name"]: i["severity"] for i in found(owner, "dnat_dead_target")}
    assert sev == {"iran-1": "warning", "iran-2": "critical"}
    assert not found(owner, "dnat_unknown_target")


def test_a_listening_destination_or_an_answering_probe_is_fine(owner, fast):
    exit_server(owner, ports=(443, 21001))
    relay(owner, rules=[rule(21001, EXIT_IP)])
    assert not found(owner, "dnat_")
    relay(owner, "iran-2", "203.0.113.2", rules=[rule(21009, EXIT_IP)], probe=probes(EXIT_IP, 21009, 0))
    assert not found(owner, "dnat_")  # the port answers though the listener list does not show it (docker, say)


def test_an_unknown_destination_is_info_while_it_answers_and_dead_when_it_refuses(owner, fast):
    relay(owner, rules=[rule(21002, "192.0.2.50"), rule(21003, "10.77.1.2")])
    [note] = found(owner, "dnat_unknown_target")
    assert note["severity"] == "info" and note["evidence"]["rules"] == ["21002 -> 192.0.2.50:21002"]  # a tunnel peer is no note
    assert not found(owner, "dnat_dead_target")
    relay(owner, "iran-2", "203.0.113.2", rules=[rule(21002, "192.0.2.50"), rule(21003, "10.77.1.2")],
          probe=probes("192.0.2.50", 21002, 100) + probes("10.77.1.2", 21003, 100, error="timeout"))
    [dead] = [i for i in found(owner, "dnat_dead_target") if i["server_name"] == "iran-2"]
    assert dead["severity"] == "critical" and dead["evidence"]["refused"] == ["21002 -> 192.0.2.50:21002"]
    assert dead["evidence"]["probe_fail_pct"] == 100 and "21003 -> 10.77.1.2:21003" in dead["evidence"]["rules"]


def test_an_offline_destination_is_left_to_the_offline_issue_and_switches_hide_the_codes(owner, fast):
    exit_server(owner)
    relay(owner, rules=[rule(21001, EXIT_IP), rule(21002, "192.0.2.50")])
    assert found(owner, "dnat_dead_target") and found(owner, "dnat_unknown_target")
    owner.put("/api/v1/settings", json={"on_dnat_dead_target": 0, "on_dnat_unknown_target": 0})
    assert not found(owner, "dnat_")
    owner.put("/api/v1/settings", json={"on_dnat_dead_target": 1})
    db = connect()
    db.execute("UPDATE servers SET last_seen=? WHERE name='nl-1'", (int(time.time()) - 3600,))
    db.close()
    assert not found(owner, "dnat_dead_target") and found(owner, "offline")


def test_probe_results_about_own_dnat_destinations_are_kept_and_nothing_else(owner):
    relay(owner, rules=[rule(21002, "192.0.2.50")], probe=probes("192.0.2.50", 21002, 0, n=1) + probes("192.0.2.99", 21002, 0, n=1))
    db = connect()
    rows = [tuple(r) for r in db.execute("SELECT target, port FROM probes")]
    db.close()
    assert rows == [("192.0.2.50", 21002)]


# ---- probe plan -------------------------------------------------------------------------------------

def test_a_relay_probes_its_own_destinations_and_the_forwards_of_the_other_relays(owner):
    exit_server(owner)
    relay(owner, rules=[rule(21001, EXIT_IP), rule(21002, "10.77.1.2"), rule(80, RELAY_IP)])
    _, _, resp = relay(owner, "iran-2", "203.0.113.2", rules=[rule(21005, "192.0.2.50")])
    got = {(t["target"], t["port"]) for t in resp["probe_targets"]}
    assert (EXIT_IP, 443) in got and ("192.0.2.50", 21005) in got
    assert {(RELAY_IP, 21001), (RELAY_IP, 21002)} <= got and (RELAY_IP, 80) not in got  # a rule to itself is no forward
    assert (EXIT_IP, 21001) not in got  # iran-1's destinations are iran-1's to probe


def test_the_extra_targets_are_capped_and_take_turns(owner, monkeypatch):
    relay(owner, rules=[rule(20000 + k, "192.0.2.%d" % (k + 1)) for k in range(20)])
    make_server(owner, "iran-2", "relay")
    from app.features.overview import probes as probes_svc
    now = [1_000_000]
    monkeypatch.setattr(probes_svc, "ROTATE_S", 1)
    db = connect()
    sid = db.execute("SELECT id FROM servers WHERE name='iran-1'").fetchone()[0]
    first = probes_svc.targets_for_relay(db, 1, now[0], sid)
    second = probes_svc.targets_for_relay(db, 1, now[0] + 1, sid)
    db.close()
    assert len(first) == probes_svc.OWN_DNAT_MAX and first != second


# ---- relay_forward_broken -------------------------------------------------------------------------

def forward_fleet(owner, fails, proven=True):
    exit_server(owner, ports=(443, 21001))
    relay(owner, rules=[rule(21001, EXIT_IP)])
    if proven:
        prove(RELAY_IP, 21001)
    for n, pct in enumerate(fails, 2):
        relay(owner, "iran-%d" % n, "203.0.113.%d" % n, rules=[rule(21001, EXIT_IP)],
              probe=probes(RELAY_IP, 21001, pct, error="timeout"))


def test_two_relays_agreeing_make_a_broken_forward_with_its_location(owner, fast):
    forward_fleet(owner, [100, 100])
    [issue] = found(owner, "relay_forward_broken")
    assert issue["severity"] == "critical" and issue["server_name"] == "iran-1"
    assert issue["code"].endswith(":21001") and issue["evidence"]["failed_from"] == ["iran-2", "iran-3"]
    assert issue["evidence"]["location_relays"] == ["iran-1", "iran-2", "iran-3"] and issue["evidence"]["location_relays_count"] == 3
    health = {s["name"]: s for s in owner.get("/api/v1/reports/health").json()["servers"]}
    assert "forward_broken" in {g["key"] for g in health["iran-1"]["gates"]}


def test_one_relay_is_info_disagreeing_relays_and_unproven_ports_are_nothing(owner, fast):
    forward_fleet(owner, [100])
    assert [i["severity"] for i in found(owner, "relay_forward_broken")] == ["info"]


def test_disagreeing_relays_point_at_the_measuring_relay_not_the_forward(owner, fast):
    forward_fleet(owner, [100, 0])
    assert not found(owner, "relay_forward_broken")


def test_a_port_that_never_answered_decides_nothing(owner, fast):
    forward_fleet(owner, [100, 100], proven=False)
    assert not found(owner, "relay_forward_broken")


def test_every_forward_broken_is_one_issue_and_the_switch_hides_it(owner, fast):
    exit_server(owner, ports=(443, 21001, 21002))
    relay(owner, rules=[rule(21001, EXIT_IP), rule(21002, EXIT_IP)])
    prove(RELAY_IP, 21001)
    prove(RELAY_IP, 21002)
    for n in (2, 3):
        relay(owner, "iran-%d" % n, "203.0.113.%d" % n,
              probe=probes(RELAY_IP, 21001, 100, error="timeout") + probes(RELAY_IP, 21002, 100, error="timeout"))
    [issue] = found(owner, "relay_forward_broken")
    assert issue["code"].endswith(":all") and issue["evidence"]["ports"] == ["tcp/21001", "tcp/21002"]
    owner.put("/api/v1/settings", json={"on_relay_forward_broken": 0})
    assert not found(owner, "relay_forward_broken")


def test_without_the_fast_fixture_a_forward_verdict_needs_six_samples_per_relay(owner):
    exit_server(owner, ports=(443, 21001))
    relay(owner, rules=[rule(21001, EXIT_IP)])
    prove(RELAY_IP, 21001)
    for n in (2, 3):
        relay(owner, "iran-%d" % n, "203.0.113.%d" % n, probe=probes(RELAY_IP, 21001, 100, error="timeout", n=5))
    assert not found(owner, "relay_forward_broken")
