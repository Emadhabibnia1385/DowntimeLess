import time

import pytest
from seed import seed_fleet

from app.db import connect
from conftest import make_server, report

PERIODIC = ["daily", "incidents", "traffic", "availability", "capacity", "relays"]


def _get(owner, path, **q):
    qs = "&".join("%s=%s" % kv for kv in q.items())
    return owner.get("/api/v1/reports/%s%s" % (path, "?" + qs if qs else ""))


@pytest.mark.parametrize("path", PERIODIC)
def test_windows_are_validated_like_the_link_traffic_endpoint(owner, path):
    now = int(time.time())
    for q in ({"since": now, "until": now - 5}, {"since": 0, "until": now}, {"since": -5, "until": now}, {"since": now - 367 * 86400, "until": now}):
        r = _get(owner, path, **q)
        assert r.status_code == 422 and r.json()["code"] == "window.invalid", (path, q)
    assert _get(owner, path, since=now - 366 * 86400, until=now).status_code == 200


def test_daily_digest_compares_with_the_previous_window(owner):
    ids, _ = seed_fleet(owner)
    d = _get(owner, "daily").json()
    assert d["since"] == d["previous_since"] + 86400
    assert d["incidents"]["opened"] == 5 and d["incidents"]["still_open"] == 1 and d["incidents"]["previous_opened"] == 1
    assert d["incidents"]["closed"] == 4 and d["incidents"]["mttr_s"] is not None
    assert d["traffic"]["total"] > 0 and d["traffic"]["previous_total"] > 0
    assert d["traffic"]["relay"] + d["traffic"]["exit"] + d["traffic"]["other"] == d["traffic"]["total"]
    assert d["top_issues"][0]["code"] == "cpu" and d["top_issues"][0]["occurrences"] == 4
    assert all(c["kind"] not in ("issue_opened", "issue_closed") for c in d["changes"])
    assert d["health"]["failing"] == 3
    md = _get(owner, "daily", format="md").text
    assert "Incidents opened 5 (previous 1)" in md and "## Top issues" in md and "## Changes" in md


def test_incidents_report_counts_mttr_flapping_and_longest(owner):
    seed_fleet(owner)
    r = _get(owner, "incidents").json()
    codes = {c["code"]: c for c in r["by_code"]}
    assert codes["cpu"]["incidents"] == 4 and codes["cpu"]["mttr_s"] == 900 and codes["disk"]["mttr_s"] == 4 * 3600
    assert [f["code"] for f in r["flapping"]] == ["cpu"] and r["flapping"][0]["server"] == "de-2"
    assert r["longest"][0]["code"] == "disk" or r["longest"][0]["code"] == "offline"
    assert r["totals"]["still_open"] == 1 and r["totals"]["critical_opened"] == 2
    assert {s["server"] for s in r["by_server"]} == {"de-2", "ir-3", "nl-1"}
    assert r["retention_days"] == 90
    md = _get(owner, "incidents", format="md").text
    assert "## By code" in md and "## Flapping" in md and "## Longest" in md


def test_incident_lists_are_capped_and_say_so(owner):
    db = connect()
    now = int(time.time())
    for n in range(40):
        db.execute("INSERT INTO incidents (key, code, server_id, server_name, severity, title, evidence, opened_at, last_seen, closed_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   ("k%d" % n, "c%d" % n, None, "s%d" % n, "warning", "t", "{}", now - 3600, now - 60, now - 60))
    db.close()
    r = _get(owner, "incidents").json()
    assert len(r["by_code"]) == 25 and len(r["by_server"]) == 25 and r["truncated"] and len(r["longest"]) == 10
    assert "(lists truncated)" in _get(owner, "incidents", format="md").text


def test_traffic_report_totals_peaks_and_pairs(owner):
    ids, _ = seed_fleet(owner)
    now = int(time.time())
    db = connect()
    db.execute("INSERT INTO link_traffic (server_id, peer_ip, hour, in_bytes, out_bytes) VALUES (?,?,?,?,?)", (ids["ir-1"], "198.51.100.12", now - now % 3600 - 3600, 111, 222))
    db.close()
    r = _get(owner, "traffic").json()
    assert r["fleet"]["total"] == r["fleet"]["rx"] + r["fleet"]["tx"] > 0
    assert len(r["servers"]) == 15 and r["servers"][0]["total"] >= r["servers"][-1]["total"]
    assert r["peak_day"]["bytes"] > 0 and r["peak_hour"]["bytes"] > 0 and 7 <= len(r["daily"]) <= 9
    assert r["link_pairs"] == [{"server": "ir-1", "server_role": "relay", "peer": "fi-1", "in_bytes": 111, "out_bytes": 222}]
    md = _get(owner, "traffic", format="md").text
    assert "## Servers" in md and "## Days (Tehran)" in md and "## Pairs" in md


def test_availability_counts_gaps_between_reports(owner):
    sid, key = make_server(owner, "de-1", "exit")
    now = int(time.time())
    db = connect()
    db.execute("DELETE FROM metrics")
    rows = [(sid, now - 3600 + k * 30) for k in range(120) if not (40 <= k < 60)]  # one ten-minute silence
    db.executemany("INSERT INTO metrics (server_id, ts, cpu) VALUES (?,?,?)", [(s, t, 1.0) for s, t in rows])
    db.close()
    r = _get(owner, "availability", since=now - 3600, until=now).json()
    row = r["servers"][0]
    assert row["server"] == "de-1" and row["outages"] >= 1
    assert 80 < row["availability_pct"] < 90 and 580 <= row["down_s"] <= 700
    assert r["fleet_availability_pct"] == row["availability_pct"]
    assert "gaps" in _get(owner, "availability", format="md").text


def test_availability_of_an_offline_incident_longer_than_the_gap_and_a_silent_server(owner):
    seed_fleet(owner)
    r = _get(owner, "availability").json()
    by = {s["server"]: s for s in r["servers"]}
    assert "new-1" not in by  # never reported: not measurable
    assert by["ir-3"]["availability_pct"] <= 100 and r["servers"][0]["availability_pct"] <= r["servers"][-1]["availability_pct"]


def test_capacity_peaks_siblings_and_growth(owner):
    ids, _ = seed_fleet(owner)
    db = connect()
    now = int(time.time())
    db.execute("UPDATE metrics SET cpu=100 WHERE server_id=? AND ts>?", (ids["de-1"], now - 86400))
    db.close()
    r = _get(owner, "capacity").json()
    by = {s["server"]: s for s in r["servers"]}
    assert r["servers"][0]["server"] == "de-1" and by["de-1"]["cpu_peak"] >= 99
    assert by["de-1"]["imbalance"] is True and by["de-2"]["imbalance"] is False
    assert by["de-1"]["sibling_group"].startswith("exit/") and by["de-1"]["vs_sibling_median"] > 20
    assert by["ir-1"]["load_per_core_peak"] is not None and by["ir-1"]["cores"] == 2
    assert by["fr-1"]["traffic_growth_pct"] is None  # no data before the window
    assert "IMBALANCE" in _get(owner, "capacity", format="md").text


def test_relay_matrix_has_verdicts_and_bytes(owner):
    ids, _ = seed_fleet(owner)
    now = int(time.time())
    db = connect()
    db.execute("INSERT INTO link_traffic (server_id, peer_ip, hour, in_bytes, out_bytes) VALUES (?,?,?,?,?)", (ids["ir-1"], "198.51.100.11", now - 7200, 5, 6))
    db.close()
    r = _get(owner, "relays").json()
    assert len(r["pairs"]) == 4 * 8 and not r["truncated"]
    v = {(p["relay"], p["exit"]): p["verdict"] for p in r["pairs"]}
    assert v[("ir-1", "de-1")] == "blacklisted" and v[("ir-2", "fi-1")] == "relay_egress" and v[("ir-4", "nl-1")] == "ok"
    assert r["problems"] == 5
    one = [p for p in r["pairs"] if (p["relay"], p["exit"]) == ("ir-1", "de-2")][0]
    assert (one["in_bytes"], one["out_bytes"]) == (5, 6)
    md = _get(owner, "relays", format="md").text
    assert "relay \\ exit" in md and "blacklisted" in md and "Bytes in window" in md


def test_one_relay_failing_to_two_exits_is_a_relay_level_filter(owner):
    r1, k1 = make_server(owner, "ir-1", "relay")
    r2, k2 = make_server(owner, "ir-2", "relay")
    report(owner, k1)
    report(owner, k2)
    db = connect()
    now = int(time.time())
    for name, ip in (("de-1", "198.51.100.1"), ("de-2", "198.51.100.2"), ("de-3", "198.51.100.3")):
        _, k = make_server(owner, name, "exit")
        report(owner, k, public_ip=ip)
        for relay, bad in ((r1, name != "de-3"), (r2, False)):
            for n in range(8):
                db.execute("INSERT INTO pings (server_id, ts, target, loss, rtt) VALUES (?,?,?,?,?)", (relay, now - 20 - n * 30, ip, 100.0 if bad else 0.0, 40.0))
    db.close()
    v = {(p["relay"], p["exit"]): p["verdict"] for p in _get(owner, "relays").json()["pairs"]}
    assert v[("ir-1", "de-1")] == "relay_filtered" and v[("ir-1", "de-2")] == "relay_filtered" and v[("ir-1", "de-3")] == "ok"


def test_reports_work_on_an_empty_panel(owner):
    for path in PERIODIC:
        assert _get(owner, path).status_code == 200
        assert _get(owner, path, format="md").text.startswith("# ")
