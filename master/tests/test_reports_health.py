import time

from app.db import connect
from conftest import make_server, report


def _health(owner):
    return {h["name"]: h for h in owner.get("/api/v1/reports/health").json()["servers"]}


def _ping(sid, target, loss, n=8):
    db = connect()
    now = int(time.time())
    for k in range(n):
        db.execute("INSERT INTO pings (server_id, ts, target, loss, rtt) VALUES (?,?,?,?,?)", (sid, now - 20 - k * 40, target, loss, 40.0))
    db.close()


def test_a_quiet_relay_is_healthy_with_a_perfect_score(owner):
    sid, key = make_server(owner, "ir-1", "relay")
    report(owner, key)
    h = _health(owner)["ir-1"]
    assert (h["score"], h["band"], h["gates"], h["penalties"]) == (100, "healthy", [], [])
    assert "forward_integrity (listeners, DNAT table)" in h["not_measured"] and "reachability_from_abroad" in h["not_measured"]


def test_penalties_move_the_score_into_degraded(owner):
    sid, key = make_server(owner, "ir-1", "relay")
    report(owner, key, tcp_retrans_pct=7.0, cpu_pct=95.0, steal_pct=18.0, ram_avail_mb=60)
    h = _health(owner)["ir-1"]
    keys = {p["key"]: p["points"] for p in h["penalties"]}
    assert keys == {"retrans": 15, "cpu_steal": 8, "memory": 5}
    assert (h["score"], h["band"], h["gates"]) == (72, "degraded", [])


def test_many_penalties_make_it_failing_without_any_gate(owner):
    sid, key = make_server(owner, "ir-1", "relay")
    exit_id, ek = make_server(owner, "de-1", "exit")
    report(owner, ek, public_ip="198.51.100.9")
    report(owner, key, tcp_retrans_pct=7.0, conntrack_pct=75.0, cpu_pct=95.0, steal_pct=45.0, ram_avail_mb=40, disk_used_gb=96, failed_units=["x.service"])
    _ping(sid, "198.51.100.9", 15.0)
    h = _health(owner)["ir-1"]
    assert h["gates"] == [] and h["score"] == 38 and h["band"] == "failing"
    assert sum(p["points"] for p in h["penalties"]) == 100 - h["score"]


def test_a_hard_gate_fails_a_server_whatever_its_score(owner):
    sid, key = make_server(owner, "ir-1", "relay")
    report(owner, key, conntrack_pct=90.0)
    h = _health(owner)["ir-1"]
    assert [g["key"] for g in h["gates"]] == ["conntrack_full"] and h["score"] >= 50 and h["band"] == "failing"


def test_offline_pending_and_unreachable_exits(owner):
    off, ok = make_server(owner, "ir-off", "relay")
    report(owner, ok)
    pend, _ = make_server(owner, "new-1", "exit")
    ex, ek = make_server(owner, "de-1", "exit")
    report(owner, ek, public_ip="198.51.100.9")
    r1, k1 = make_server(owner, "ir-1", "relay")
    r2, k2 = make_server(owner, "ir-2", "relay")
    report(owner, k1)
    report(owner, k2)
    _ping(r1, "198.51.100.9", 100.0)
    _ping(r2, "198.51.100.9", 100.0)
    db = connect()
    db.execute("UPDATE servers SET last_seen=? WHERE id=?", (int(time.time()) - 900, off))
    db.close()
    h = _health(owner)
    assert (h["ir-off"]["score"], h["ir-off"]["band"], h["ir-off"]["gates"][0]["key"]) == (0, "failing", "agent_offline")
    assert (h["new-1"]["score"], h["new-1"]["band"]) == (None, "unknown")
    assert h["de-1"]["gates"][0]["key"] == "unreachable_from_all_relays" and h["de-1"]["band"] == "failing"
    assert {p["key"] for p in h["de-1"]["penalties"]} == {"relay_reachability"}
    assert "listener_completeness" in h["de-1"]["not_measured"]


def test_one_relay_failing_is_a_penalty_not_a_gate_for_the_exit(owner):
    ex, ek = make_server(owner, "de-1", "exit")
    report(owner, ek, public_ip="198.51.100.9")
    r1, k1 = make_server(owner, "ir-1", "relay")
    r2, k2 = make_server(owner, "ir-2", "relay")
    report(owner, k1)
    report(owner, k2)
    _ping(r1, "198.51.100.9", 100.0)
    _ping(r2, "198.51.100.9", 0.0)
    h = _health(owner)
    assert h["de-1"]["gates"] == [] and h["de-1"]["score"] == 100 - 13 and h["de-1"]["band"] == "healthy"
    assert h["ir-1"]["gates"][0]["key"] == "all_exits_lossy"  # its only measured exit is unreachable from it


def test_quota_gate_and_penalty_switch_on_when_quota_columns_exist(owner):
    sid, key = make_server(owner, "ir-1", "relay")
    report(owner, key)
    assert owner.get("/api/v1/reports/health").json()["quota_measured"] is False
    b = owner.get("/api/v1/reports/briefing").json()
    assert b["quota"] == [] and any("quota" in x for x in b["not_measured"])
    db = connect()
    db.execute("UPDATE servers SET quota_gb=1 WHERE id=?", (sid,))
    db.execute("UPDATE metrics SET rx_delta=1100000000, tx_delta=1100000000 WHERE server_id=?", (sid,))
    db.close()
    h = owner.get("/api/v1/reports/health").json()
    assert h["quota_measured"] is True
    relay = {s["name"]: s for s in h["servers"]}["ir-1"]
    assert [g["key"] for g in relay["gates"]] == ["quota_exhausted"]
    q = owner.get("/api/v1/reports/briefing").json()["quota"]
    assert q[0]["server_name"] == "ir-1" and q[0]["used_pct"] >= 100
