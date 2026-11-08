import time

from app.db import connect
from conftest import make_server, report


def _two(owner):
    relay, rk = make_server(owner, "relay-a", "relay")
    exit_, ek = make_server(owner, "exit-b", "exit")
    report(owner, rk, public_ip="203.0.113.10")
    report(owner, ek, public_ip="198.51.100.20")
    return relay, rk, exit_, ek


def test_peers_are_sent_only_to_servers_with_counting_switched_on(owner):
    relay, rk, exit_, ek = _two(owner)
    assert report(owner, rk).json()["acct_peers"] == []
    assert owner.patch("/api/v1/servers/%d" % relay, json={"acct_on": True}).json()["acct_on"] is True
    assert report(owner, rk).json()["acct_peers"] == ["198.51.100.20"]
    assert report(owner, ek).json()["acct_peers"] == []
    owner.patch("/api/v1/servers/%d" % relay, json={"acct_on": False})
    assert report(owner, rk).json()["acct_peers"] == []


def test_cumulative_counters_become_hourly_bytes_and_a_reset_counts_as_zero(owner):
    relay, rk, exit_, ek = _two(owner)
    owner.patch("/api/v1/servers/%d" % relay, json={"acct_on": True})
    peer = "198.51.100.20"
    report(owner, rk, acct={peer: {"in": 1000, "out": 5000}})   # baseline, nothing counted yet
    report(owner, rk, acct={peer: {"in": 1600, "out": 9000}})   # +600 in, +4000 out
    report(owner, rk, acct={peer: {"in": 100, "out": 200}})     # counters restarted: zero this time
    report(owner, rk, acct={peer: {"in": 400, "out": 700}})     # +300 / +500
    links = owner.get("/api/v1/links/traffic").json()["links"]
    assert len(links) == 1
    row = links[0]
    assert (row["server_name"], row["peer_name"], row["peer_id"]) == ("relay-a", "exit-b", exit_)
    assert (row["in_bytes"], row["out_bytes"]) == (900, 4500)


def test_bad_counters_are_ignored(owner):
    relay, rk, exit_, ek = _two(owner)
    report(owner, rk, acct={"not-an-ip": {"in": 1, "out": 1}, "198.51.100.20": {"in": -5, "out": "x"}, "203.0.113.99": "bad"})
    db = connect()
    assert db.execute("SELECT COUNT(*) c FROM link_traffic").fetchone()["c"] == 0
    db.close()


def test_window_and_series_and_permissions(owner):
    relay, rk, exit_, ek = _two(owner)
    peer = "198.51.100.20"
    now = int(time.time())
    db = connect()
    db.execute("INSERT INTO link_traffic (server_id, peer_ip, hour, in_bytes, out_bytes) VALUES (?,?,?,?,?)", (relay, peer, now - now % 3600 - 7200, 10, 20))
    db.execute("INSERT INTO link_traffic (server_id, peer_ip, hour, in_bytes, out_bytes) VALUES (?,?,?,?,?)", (relay, peer, now - now % 3600 - 10 * 86400, 1000, 2000))
    db.close()
    got = owner.get("/api/v1/links/traffic?since=%d&until=%d" % (now - 86400, now)).json()["links"]
    assert [(r["in_bytes"], r["out_bytes"]) for r in got] == [(10, 20)]
    pts = owner.get("/api/v1/links/traffic/series?server_id=%d&peer_ip=%s&since=%d&until=%d" % (relay, peer, now - 86400, now)).json()["points"]
    assert [(p["in_bytes"], p["out_bytes"]) for p in pts] == [(10, 20)]
    bad = owner.get("/api/v1/links/traffic?since=%d&until=%d" % (now, now - 5))
    assert bad.status_code == 422 and bad.json()["code"] == "window.invalid"
    assert owner.get("/api/v1/links/traffic?since=0&until=%d" % now).status_code == 422  # wider than a year
    owner.cookies.clear()
    assert owner.get("/api/v1/links/traffic").status_code == 401
