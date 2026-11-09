"""Config drift from agent 0.3.3 `checks.drift`: numbers that must hold ten minutes before they are an issue."""
import time

import pytest

from checks_data import checks
from conftest import make_server, report


@pytest.fixture
def clock(monkeypatch):
    now = [float(int(time.time()))]
    real = time.time
    monkeypatch.setattr(time, "time", lambda: now[0])
    yield now
    monkeypatch.setattr(time, "time", real)


def drift(ipset=None, dnat=None, sysctl=None):
    return {"ipset": ipset, "dnat": dnat, "sysctl": sysctl}


IPSET_BAD = [{"set": "nyxon_trusted", "live": 8, "file": 21, "source": "/etc/nyxon/access.conf", "key": "TRUSTED_SOURCES",
              "file_hash": "abcdef012345"}]
DNAT_BAD = [{"table": "relay_dnat", "file": "/etc/nftables-relay-dnat.nft", "live": 7, "file_rules": 7, "live_hash": "a" * 12,
             "file_hash": "b" * 12, "ports": [19444]}]
SYSCTL_BAD = {"checked": 6, "absent": [], "mismatch": [
    {"key": "net.netfilter.nf_conntrack_tcp_timeout_established", "live": "432000", "file": "10800", "source": "/etc/sysctl.d/99-relay-dnat.conf"}]}


def send(owner, key, clock, step=60, **d):
    clock[0] += step
    r = report(owner, key, agent_version="0.3.3", uptime_s=100000 + int(clock[0]) % 100000, checks=checks(drift=drift(**d)))
    assert r.status_code == 200, r.text


def codes(owner):
    return {i["code"]: i for i in owner.get("/api/v1/issues").json() if i["code"].startswith("drift_")}


def test_drift_needs_ten_minutes_with_the_same_numbers(owner, clock):
    _, key = make_server(owner, "ir-1", "relay")
    send(owner, key, clock, ipset=IPSET_BAD, dnat=DNAT_BAD, sysctl=SYSCTL_BAD)
    assert codes(owner) == {}
    send(owner, key, clock, step=300, ipset=IPSET_BAD, dnat=DNAT_BAD, sysctl=SYSCTL_BAD)
    assert codes(owner) == {}
    send(owner, key, clock, step=320, ipset=IPSET_BAD, dnat=DNAT_BAD, sysctl=SYSCTL_BAD)
    found = codes(owner)
    assert set(found) == {"drift_ipset", "drift_dnat", "drift_sysctl"}
    ip = found["drift_ipset"]
    assert ip["severity"] == "warning" and ip["evidence"]["live"] == 8 and ip["evidence"]["file"] == 21
    assert ip["evidence"]["sets"] == ["nyxon_trusted: 8 / 21 (/etc/nyxon/access.conf)"]
    assert found["drift_dnat"]["evidence"]["ports"] == ["tcp/19444"]
    sc = found["drift_sysctl"]["evidence"]
    assert sc["keys"] == ["net.netfilter.nf_conntrack_tcp_timeout_established"] and sc["values"] == [
        "net.netfilter.nf_conntrack_tcp_timeout_established: 432000 / 10800"]


def test_a_new_number_restarts_the_clock_and_equal_numbers_clear_it(owner, clock):
    _, key = make_server(owner, "ir-1", "relay")
    send(owner, key, clock, ipset=IPSET_BAD)
    send(owner, key, clock, step=700, ipset=IPSET_BAD)
    assert "drift_ipset" in codes(owner)
    changed = [dict(IPSET_BAD[0], live=20)]
    send(owner, key, clock, ipset=changed)
    assert "drift_ipset" not in codes(owner)
    fixed = [dict(IPSET_BAD[0], live=21)]
    send(owner, key, clock, step=900, ipset=fixed)
    assert codes(owner) == {}


def test_more_live_entries_is_info_and_live_rules_without_a_file_are_drift(owner, clock):
    _, key = make_server(owner, "ir-1", "relay")
    more = [dict(IPSET_BAD[0], live=25)]
    lone = [{"table": "mobin_dnat", "file": None, "live": 3, "file_rules": None, "live_hash": "c" * 12, "file_hash": None, "ports": []}]
    send(owner, key, clock, ipset=more, dnat=lone)
    send(owner, key, clock, step=700, ipset=more, dnat=lone)
    found = codes(owner)
    assert found["drift_ipset"]["severity"] == "info"
    assert found["drift_dnat"]["evidence"]["without_file"] == ["mobin_dnat"]


def test_no_drift_block_or_an_odd_one_is_silent_and_the_switch_hides_it(owner, clock):
    _, key = make_server(owner, "ir-1", "relay")
    for _ in range(3):
        clock[0] += 400
        report(owner, key, agent_version="0.3.2", checks=checks())
        clock[0] += 400
        report(owner, key, agent_version="0.3.3", checks=checks(drift={"ipset": "junk", "dnat": [1, None], "sysctl": []}))
    assert codes(owner) == {}
    send(owner, key, clock, sysctl=SYSCTL_BAD)
    send(owner, key, clock, step=700, sysctl=SYSCTL_BAD)
    assert "drift_sysctl" in codes(owner)
    owner.put("/api/v1/settings", json={"on_drift_sysctl": 0})
    assert codes(owner) == {}
