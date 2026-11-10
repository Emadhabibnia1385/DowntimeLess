"""Phase 2 rules from agent 0.3.x `checks`: positive, negative, debounce, memory across reports, and no alarm without checks."""
import time

import pytest

from app.db import connect
from checks_data import checks
from conftest import make_server, report

DAY = 86400


@pytest.fixture
def clock(monkeypatch):
    """A controllable wall clock for every module (the agent router, the rules, the status)."""
    now = [float(int(time.time()))]
    real = time.time
    monkeypatch.setattr(time, "time", lambda: now[0])
    yield now
    monkeypatch.setattr(time, "time", real)


def send(owner, key, clock, step=30, **over):
    clock[0] += step
    body = {"agent_version": "0.3.1", "uptime_s": int(clock[0]) % 1000000 + 100000, "checks": checks()}
    body.update(over)
    r = report(owner, key, **body)
    assert r.status_code == 200, r.text
    return r


def found(owner, prefix=""):
    return {i["code"]: i for i in owner.get("/api/v1/issues").json() if i["code"].startswith(prefix)}


def learn(owner, key, clock, sid):
    """Two reports, then age the rows so the ports count as seen for more than a day."""
    send(owner, key, clock)
    send(owner, key, clock)
    db = connect()
    db.execute("UPDATE listener_baseline SET first_seen=first_seen-? WHERE server_id=?", (DAY + 10, sid))
    db.close()
    send(owner, key, clock)
    send(owner, key, clock)


def without(port, proto="tcp"):
    from checks_data import LISTENERS
    return checks(listeners=[x for x in LISTENERS if not (x["port"] == port and x["proto"] == proto)])


# ---- listeners -----------------------------------------------------------------------------------

def test_baseline_needs_a_day_and_skips_udp_summary_and_ephemeral(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    send(owner, key, clock)
    h = owner.get("/api/v1/servers/%d/host-health" % sid).json()
    assert h["has_checks"] and h["listeners"]["baseline"] == 0 and h["listeners"]["learning"] == 4  # port 0 and udp 51820 (ephemeral range) dropped
    learn(owner, key, clock, sid)
    h = owner.get("/api/v1/servers/%d/host-health" % sid).json()
    assert h["listeners"]["baseline"] == 4
    db = connect()
    ports = {r["port"] for r in db.execute("SELECT port FROM listener_baseline WHERE server_id=?", (sid,))}
    db.close()
    assert 0 not in ports and 51820 not in ports


def test_loopback_only_listeners_never_join_the_baseline(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    inner = {"proto": "tcp", "port": 40123, "proc": "xray", "addr": "127.0.0.1"}  # xray's internal port, new on every start
    send(owner, key, clock, checks=checks(listeners=checks()["listeners"] + [inner]))
    db = connect()
    assert not db.execute("SELECT 1 FROM listener_baseline WHERE server_id=? AND port=40123", (sid,)).fetchone()
    assert db.execute("SELECT 1 FROM listener_baseline WHERE server_id=? AND port=443", (sid,)).fetchone()
    db.close()


def test_a_young_port_that_disappears_is_forgotten_not_alarmed(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    send(owner, key, clock)
    for _ in range(4):
        send(owner, key, clock, checks=without(8443))
    assert "listener_missing" not in found(owner)
    db = connect()
    assert not db.execute("SELECT 1 FROM listener_baseline WHERE server_id=? AND port=8443", (sid,)).fetchone()
    db.close()


def test_missing_listener_needs_two_reports_and_is_critical_on_a_relay(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    learn(owner, key, clock, sid)
    send(owner, key, clock, checks=without(443))
    assert "listener_missing" not in found(owner)
    send(owner, key, clock, checks=without(443))
    issue = found(owner)["listener_missing"]
    assert issue["severity"] == "critical" and issue["evidence"]["ports"] == ["tcp/443"] and issue["evidence"]["procs"] == ["xray"]
    send(owner, key, clock)  # back: the counter clears at once
    assert "listener_missing" not in found(owner)


def test_missing_listener_is_a_warning_on_other_roles(owner, clock):
    sid, key = make_server(owner, "tools", "other")
    learn(owner, key, clock, sid)
    send(owner, key, clock, checks=without(22))
    send(owner, key, clock, checks=without(22))
    assert found(owner)["listener_missing"]["severity"] == "warning"


def test_after_an_agent_restart_it_takes_three_reports(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    learn(owner, key, clock, sid)
    send(owner, key, clock, agent_version="0.3.2", checks=without(443))  # new version: the agent started again
    send(owner, key, clock, agent_version="0.3.2", checks=without(443))
    assert "listener_missing" not in found(owner)
    send(owner, key, clock, agent_version="0.3.2", checks=without(443))
    assert "listener_missing" in found(owner)


def test_no_checks_never_alarms_and_never_moves_the_counter(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    learn(owner, key, clock, sid)
    for _ in range(4):
        send(owner, key, clock, checks=None)  # an old agent, or the field is gone
    send(owner, key, clock, checks={"listeners": None, "units": "broken", "containers": 7})
    assert not set(found(owner)) & {"listener_missing", "unit_stopped", "container_down"}
    db = connect()
    assert {r["missing"] for r in db.execute("SELECT missing FROM listener_baseline WHERE server_id=?", (sid,))} == {0}
    db.close()
    # an agent 0.2 report has no checks at all
    clock[0] += 30
    report(owner, key, agent_version="0.2.8")
    assert not found(owner, "listener") and owner.get("/api/v1/servers/%d/host-health" % sid).json()["has_checks"] is False


def test_owner_drops_a_port_from_the_baseline(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    learn(owner, key, clock, sid)
    send(owner, key, clock, checks=without(8443))
    send(owner, key, clock, checks=without(8443))
    assert "listener_missing" in found(owner)
    card = owner.get("/api/v1/servers/%d/host-health" % sid).json()
    assert card["listeners"]["missing"][0]["port"] == 8443 and card["listeners"]["missing"][0]["alerting"]
    r = owner.patch("/api/v1/servers/%d/listeners" % sid, json={"proto": "tcp", "port": 8443})
    assert r.status_code == 200 and r.json()["listeners"]["missing"] == []
    assert "listener_missing" not in found(owner)
    assert owner.patch("/api/v1/servers/%d/listeners" % sid, json={"proto": "tcp", "port": 8443}).json()["code"] == "listener.not_found"
    kinds = [e["kind"] for e in owner.get("/api/v1/reports/changes").json()["events"]]
    assert "check_ack" in kinds


# ---- units -----------------------------------------------------------------------------------------

def unit(name, active="active", sub="running", restarts=0, enabled=True):
    return {"name": name, "enabled": enabled, "active": active, "sub": sub, "restarts": restarts}


def test_enabled_tunnel_unit_stopped_is_critical_and_other_families_are_skipped(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    send(owner, key, clock, checks=checks(units=[unit("backhaul-de.service", "inactive", "dead"), unit("nginx.service", "inactive", "dead"),
                                                 unit("gre-de.service", "active", "exited"), unit("backpack-x.service", "inactive", "dead", enabled=False)]))
    issue = found(owner)["unit_stopped"]
    assert issue["severity"] == "critical" and issue["evidence"]["units"] == ["backhaul-de.service"]


def test_crash_loop_from_auto_restart_or_rising_restarts(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    send(owner, key, clock, checks=checks(units=[unit("backpack-a.service", restarts=1)]))
    send(owner, key, clock, checks=checks(units=[unit("backpack-a.service", restarts=2)]))
    assert "unit_crashloop" not in found(owner)
    send(owner, key, clock, checks=checks(units=[unit("backpack-a.service", restarts=4)]))
    issue = found(owner)["unit_crashloop"]
    assert issue["severity"] == "warning" and issue["evidence"]["restarts_10m"] == ["backpack-a.service +3"]
    # quiet for more than ten minutes: the window forgets the restarts
    send(owner, key, clock, step=700, checks=checks(units=[unit("backpack-a.service", restarts=4)]))
    assert "unit_crashloop" not in found(owner)
    # a unit that owns forward ports in auto-restart is critical
    send(owner, key, clock, checks=checks(units=[unit("backhaul-de.service", "activating", "auto-restart", 9)]))
    assert found(owner)["unit_crashloop"]["severity"] == "critical"


# ---- containers ------------------------------------------------------------------------------------

def box(name="pasarguard-node-1", state="running", restarts=0, policy="always", exit_code=0, health=None, started_at=1):
    return {"name": name, "image": "pasarguard/node:latest", "state": state, "status": "", "restarts": restarts, "health": health,
            "policy": policy, "exit_code": exit_code, "oom_killed": False, "started_at": started_at}


def test_container_that_was_running_and_stopped_is_down(owner, clock):
    sid, key = make_server(owner, "de-1", "exit")
    send(owner, key, clock, checks=checks(containers=[box(policy="no")]))
    send(owner, key, clock, checks=checks(containers=[box(state="exited", policy="no", exit_code=0)]))
    issue = found(owner)["container_down"]
    assert issue["severity"] == "critical" and issue["evidence"]["containers"] == ["pasarguard-node-1 (exited, 0)"]
    send(owner, key, clock, checks=checks(containers=[box(policy="no")]))
    assert "container_down" not in found(owner)


def test_exited_container_with_policy_always_is_down_but_a_clean_unless_stopped_is_not(owner, clock):
    sid, key = make_server(owner, "de-1", "exit")
    send(owner, key, clock, checks=checks(containers=[box("panel-old", "exited", policy="unless-stopped", exit_code=137),
                                                      box("node-b", "exited", policy="always", exit_code=137)]))
    assert found(owner)["container_down"]["evidence"]["containers"] == ["node-b (exited, 137)"]
    send(owner, key, clock, checks=checks(containers=[box("panel-old", "exited", policy="unless-stopped", exit_code=1)]))
    assert found(owner)["container_down"]["evidence"]["containers"] == ["panel-old (exited, 1)"]


def test_a_retired_container_never_alarms(owner, clock):
    sid, key = make_server(owner, "de-1", "exit")
    send(owner, key, clock, checks=checks(containers=[box("node-b", "exited", policy="always", exit_code=1)]))
    assert "container_down" in found(owner)
    assert owner.patch("/api/v1/servers/%d/ignores" % sid, json={"kind": "container", "name": "node-b"}).status_code == 200
    assert "container_down" not in found(owner)
    assert owner.get("/api/v1/servers/%d/host-health" % sid).json()["containers"][0]["retired"] is True
    owner.patch("/api/v1/servers/%d/ignores" % sid, json={"kind": "container", "name": "node-b", "ignored": False})
    assert "container_down" in found(owner)
    assert owner.patch("/api/v1/servers/%d/ignores" % sid, json={"kind": "node", "name": "abc"}).json()["code"] == "check.invalid"


def test_restarting_unhealthy_and_revived_containers(owner, clock):
    sid, key = make_server(owner, "de-1", "exit")
    send(owner, key, clock, checks=checks(containers=[box(restarts=5), box("panel", "exited", policy="always", exit_code=137)]))
    send(owner, key, clock, checks=checks(containers=[box(restarts=8, health="unhealthy"), box("panel", "exited", policy="always", exit_code=137)]))
    got = found(owner)
    assert got["container_restarting"]["evidence"]["containers"] == ["pasarguard-node-1 +3"]
    assert got["container_unhealthy"]["evidence"]["containers"] == ["pasarguard-node-1"]
    # the host reboots and the stopped panel comes back by itself
    send(owner, key, clock, uptime_s=60, checks=checks(containers=[box(), box("panel", started_at=int(clock[0]) + 20)]))
    got = found(owner)
    assert got["container_revived"]["severity"] == "info" and got["container_revived"]["evidence"]["containers"] == ["panel"]
    assert "container_down" not in got


# ---- DNAT and kernel -------------------------------------------------------------------------------

def test_dnat_that_was_there_and_is_gone_is_critical_after_two_reports(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    gone = {"tables": ["inet filter"], "relay_dnat": False, "dnat_rules": 0, "dnat_by_table": {}, "ip_forward": 1}
    send(owner, key, clock)
    send(owner, key, clock, checks=checks(nft=gone))
    assert "dnat_missing" not in found(owner)
    send(owner, key, clock, checks=checks(nft=gone))
    issue = found(owner)["dnat_missing"]
    assert issue["severity"] == "critical" and issue["evidence"]["had_rules"] == 12
    send(owner, key, clock, checks=checks(nft=None))  # the collector failed: no verdict either way
    assert "dnat_missing" not in found(owner)
    owner.patch("/api/v1/servers/%d/ignores" % sid, json={"kind": "dnat"})  # removed on purpose
    send(owner, key, clock, checks=checks(nft=gone))
    send(owner, key, clock, checks=checks(nft=gone))
    assert "dnat_missing" not in found(owner)


def test_a_server_that_never_had_dnat_is_quiet(owner, clock):
    sid, key = make_server(owner, "de-1", "exit")
    for _ in range(3):
        send(owner, key, clock, checks=checks(nft={"tables": [], "relay_dnat": False, "dnat_rules": 0, "ip_forward": 0}))
    assert not set(found(owner)) & {"dnat_missing", "ip_forward_off"}


def test_ip_forward_off_is_critical_on_a_forwarding_relay(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    send(owner, key, clock, checks=checks(nft={"tables": ["ip relay_dnat"], "relay_dnat": True, "dnat_rules": 3, "ip_forward": 0}))
    assert found(owner)["ip_forward_off"]["severity"] == "critical"


def test_conntrack_limits_reset_per_role(owner, clock):
    relay, rkey = make_server(owner, "ir-1", "relay")
    exit_, ekey = make_server(owner, "de-1", "exit")
    ct = {"module_loaded": True, "count": 100, "max": 131072, "tcp_established_timeout": 7200, "insert_failed": 0, "drop": 0}
    send(owner, rkey, clock, checks=checks(conntrack=ct))
    send(owner, ekey, clock, checks=checks(conntrack=ct))
    got = [i for i in owner.get("/api/v1/issues").json() if i["code"] == "conntrack_limits_reset"]
    assert [i["server_id"] for i in got] == [exit_] and got[0]["evidence"]["expected_max"] == 262144
    send(owner, rkey, clock, checks=checks(conntrack=dict(ct, max=8192, tcp_established_timeout=432000)))
    got = {i["server_id"]: i for i in owner.get("/api/v1/issues").json() if i["code"] == "conntrack_limits_reset"}
    assert got[relay]["evidence"]["tcp_established_timeout_s"] == 432000
    owner.put("/api/v1/settings", json={"ct_max_exit": 100000})
    assert exit_ not in {i["server_id"] for i in owner.get("/api/v1/issues").json() if i["code"] == "conntrack_limits_reset"}


def test_conntrack_drops_and_oom_kills_are_increases_not_levels(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    base = checks()
    high = checks(conntrack=dict(base["conntrack"], insert_failed=500, drop=20), kernel=dict(base["kernel"], oom_kill=3))
    send(owner, key, clock, checks=high)  # high but steady counters from boot are not an alarm
    send(owner, key, clock, checks=high)
    assert not set(found(owner)) & {"conntrack_drops", "oom_kill"}
    send(owner, key, clock, checks=checks(conntrack=dict(base["conntrack"], insert_failed=530, drop=25), kernel=dict(base["kernel"], oom_kill=4)))
    got = found(owner)
    assert got["conntrack_drops"]["severity"] == "critical" and got["conntrack_drops"]["evidence"]["insert_failed_delta"] == 30
    assert got["oom_kill"]["evidence"]["oom_kills"] == 1
    # a reboot resets the counters: lower values are a new start, and the alarm fades after 30 minutes
    send(owner, key, clock, step=1900, checks=base)
    assert not set(found(owner)) & {"conntrack_drops", "oom_kill"}


def test_insert_failed_on_an_almost_empty_table_is_not_an_alert(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    base = checks()
    send(owner, key, clock, checks=base)
    send(owner, key, clock, checks=base)
    send(owner, key, clock, checks=checks(conntrack=dict(base["conntrack"], insert_failed=900)))  # a DNS/UDP race, table 1% full
    assert "conntrack_drops" not in found(owner)
    full = dict(base["conntrack"], count=700000, insert_failed=950)
    send(owner, key, clock, checks=checks(conntrack=full))  # the same counter with a filling table is real
    assert "conntrack_drops" in found(owner)


def test_inodes_journal_time_and_reboot_packages(owner, clock):
    sid, key = make_server(owner, "de-1", "exit")
    k = checks()["kernel"]
    send(owner, key, clock, reboot_required=True,
         checks=checks(kernel=dict(k, inode_pct=91.5, journal_mb=4096.0, ntp_synced=False), apt={"dpkg_audit": 0, "reboot_required_pkgs": 3}))
    got = found(owner)
    assert got["inode_high"]["evidence"]["inode_pct"] == 91.5 and got["journal_big"]["severity"] == "warning"
    assert "time_unsynced" not in got  # needs ten minutes
    assert got["reboot_pending_pkgs"]["severity"] == "info" and "reboot_required" not in got  # replaces the bare flag
    send(owner, key, clock, step=660, reboot_required=True,
         checks=checks(kernel=dict(k, ntp_synced=False), apt={"dpkg_audit": 2, "reboot_required_pkgs": 3}))
    got = found(owner)
    assert got["time_unsynced"]["evidence"]["unsynced_s"] >= 600
    assert got["reboot_pending_pkgs"]["severity"] == "warning"  # dpkg is half-configured: the reboot is a gamble


def test_switches_turn_each_rule_off(owner, clock):
    sid, key = make_server(owner, "de-1", "exit")
    owner.put("/api/v1/settings", json={"on_inode_high": 0})
    send(owner, key, clock, checks=checks(kernel=dict(checks()["kernel"], inode_pct=99.0)))
    assert "inode_high" not in found(owner)
    assert owner.get("/api/v1/settings").json()["on_listener_missing"] == 1


def test_oddly_shaped_fields_never_break_the_report_or_the_issues(owner, clock):
    sid, key = make_server(owner, "de-1", "exit")
    weird = {"listeners": [{"proto": "tcp", "port": "443"}, "x", {"proto": "sctp", "port": 5}], "units": [{"name": 5}, {}],
             "containers": [{"name": None}, {"name": "a", "state": 3, "restarts": "many"}], "nft": {"relay_dnat": "yes"},
             "conntrack": {"module_loaded": "true", "max": "big"}, "kernel": {"oom_kill": None, "inode_pct": "90"},
             "apt": [], "tunnels": "none"}
    send(owner, key, clock, checks=weird, panel=[1, 2], panel_error=5)
    send(owner, key, clock, checks=weird)
    assert owner.get("/api/v1/issues").status_code == 200
    assert owner.get("/api/v1/servers/%d/host-health" % sid).status_code == 200
    assert owner.get("/api/v1/panel").json()["panels"] == []


def test_briefing_and_health_carry_the_new_issues(owner, clock):
    sid, key = make_server(owner, "ir-1", "relay")
    gone = {"tables": [], "relay_dnat": False, "dnat_rules": 0, "ip_forward": 1}
    send(owner, key, clock)
    send(owner, key, clock, checks=checks(nft=gone))
    send(owner, key, clock, checks=checks(nft=gone))
    b = owner.get("/api/v1/reports/briefing?detail=full").json()
    assert "dnat_missing" in [i["code"] for i in b["issues"]["items"]]
    assert b["host_checks"]["reporting"] == 1 and b["host_checks"]["problems"][0]["code"] == "dnat_missing"
    assert b["check_first"][0]["code"] == "dnat_missing"
    md = owner.get("/api/v1/reports/briefing?format=md").text
    assert "## Host checks" in md and "dnat_missing" in md
    h = [s for s in owner.get("/api/v1/reports/health").json()["servers"] if s["server_id"] == sid][0]
    assert h["band"] == "failing" and "dnat_missing" in [g["key"] for g in h["gates"]]
    assert any(p["key"] == "forward_integrity" for p in h["penalties"])
    assert not any(x.startswith("host checks") for x in h["not_measured"])


def test_every_new_rule_has_a_switch_a_route_and_its_codes_map_to_it():
    from app.alerts import DEFAULT_ROUTES, rule_of
    from app.features.reports import playbooks
    from app.features.settings.router import DEFAULTS, RULES
    raised = set(playbooks.raised_codes())
    for code in ("listener_missing", "unit_stopped", "container_down", "dnat_missing", "node_down", "node_silent", "reseller_quota",
                 "conntrack_drops", "oom_kill", "panel_errors"):
        assert code in RULES and DEFAULTS["on_" + code] == 1 and code in raised
    assert rule_of("node_down:5") == "node_down" and rule_of("reseller_quota:reseller03") == "reseller_quota"
    assert DEFAULT_ROUTES["listener_missing"] == "admins" and DEFAULT_ROUTES["panel_errors"] == "panel"


def test_a_critical_check_issue_reaches_telegram(owner, clock, tg):
    from app import monitor
    sid, key = make_server(owner, "ir-1", "relay")
    gone = {"tables": [], "relay_dnat": False, "dnat_rules": 0, "ip_forward": 1}
    send(owner, key, clock)
    send(owner, key, clock, checks=checks(nft=gone))
    send(owner, key, clock, checks=checks(nft=gone))
    monitor.sweep(tg)
    assert any("DNAT" in text for _, text, _ in tg.sent)
