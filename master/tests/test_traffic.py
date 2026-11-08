import random
from datetime import datetime, timedelta, timezone

import pytest

from app.db import connect
from app.features.traffic import service as svc
from conftest import make_server

TZ = 210  # Iran, +03:30
IRAN = timezone(timedelta(minutes=TZ))
GB = 10**9


def at(y, m, d, h=0, mi=0, s=0, tz=IRAN):
    return int(datetime(y, m, d, h, mi, s, tzinfo=tz).timestamp())


NOW = at(2027, 2, 3, 12, 30)  # Wednesday midday local, the month started two days ago


@pytest.fixture
def fixed_now(monkeypatch):
    holder = {"now": NOW}
    monkeypatch.setattr("app.features.traffic.router._now", lambda: holder["now"])
    return holder


def put(sid, ts, rx=0, tx=0):
    db = connect()
    db.execute("INSERT INTO metrics (server_id, ts, rx_delta, tx_delta) VALUES (?,?,?,?)", (sid, ts, rx, tx))
    db.close()


def summary(client, query=""):
    r = client.get("/api/v1/traffic/summary?" + query)
    assert r.status_code == 200, r.text
    return r.json()


def series(client, query):
    r = client.get("/api/v1/traffic/series?" + query)
    assert r.status_code == 200, r.text
    return r.json()


def window(a, b):
    return "since=%d&until=%d" % (a, b)


def test_calendar_helpers_match_datetime():
    rng = random.Random(7)
    for _ in range(300):
        tz = rng.randint(svc.TZ_MIN, svc.TZ_MAX)
        ts = rng.randint(at(2020, 1, 1, tz=timezone.utc), at(2035, 1, 1, tz=timezone.utc))
        local = datetime.fromtimestamp(ts, timezone(timedelta(minutes=tz)))
        mid = int(local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        assert svc.local_midnight(ts, tz * 60) == mid
        assert svc.day_label(mid, tz * 60) == local.strftime("%Y-%m-%d")


def test_empty_fleet(owner, fixed_now):
    data = summary(owner)
    assert data["servers"] == [] and data["fleet"]["today"] == {"rx": 0, "tx": 0, "total": 0}
    assert data["fleet"]["peak_day"] is None and data["fleet"]["active_days"] == 0
    s = series(owner, "range=24h")
    assert len(s["points"]) == 24 and s["rx_total"] == 0 and s["top_days"] == []
    assert [p["hour"] for p in s["hour_profile"]] == list(range(24)) and all(p["rx"] == 0 for p in s["hour_profile"])


def test_server_without_data_is_listed_with_zeros(owner, fixed_now):
    sid, _ = make_server(owner, "de-1")
    (row,) = summary(owner)["servers"]
    assert row["server_id"] == sid and row["name"] == "de-1" and row["role"] == "exit"
    assert row["period"]["total"] == 0 and row["peak_day"] is None and row["share_pct"] == 0


def test_today_and_yesterday_are_local_days_and_the_default_window_is_30_days(owner, fixed_now):
    sid, _ = make_server(owner)
    put(sid, at(2027, 2, 3, 0, 0, 0), 1 * GB, 2 * GB)  # first second of today, still 20:30 UTC yesterday
    put(sid, at(2027, 2, 2, 23, 59, 59), 10 * GB, 20 * GB)  # last second of yesterday
    put(sid, at(2027, 1, 5, 0, 0, 0), 3 * GB)  # first second of the default 30-day window
    put(sid, at(2027, 1, 4, 23, 59, 59), 9 * GB)  # one second before it
    put(sid, NOW + 60, 500 * GB)  # a clock-skewed future sample never counts
    data = summary(owner)
    (row,) = data["servers"]
    assert row["today"] == {"rx": GB, "tx": 2 * GB, "total": 3 * GB}
    assert row["yesterday"] == {"rx": 10 * GB, "tx": 20 * GB, "total": 30 * GB}
    assert row["period"]["rx"] == 14 * GB and data["since"] == at(2027, 1, 5)


def test_explicit_windows_cover_whole_local_days(owner, fixed_now):
    sid, _ = make_server(owner)
    put(sid, at(2027, 1, 31, 23, 59, 59), 1 * GB)  # last second of January
    put(sid, at(2027, 2, 1, 0, 0, 0), 2 * GB)  # first second of February
    put(sid, at(2027, 2, 3, 9), 4 * GB)
    jan = summary(owner, window(at(2027, 1, 1), at(2027, 2, 1)))["servers"][0]
    feb = summary(owner, window(at(2027, 2, 1), at(2027, 3, 1)))["servers"][0]
    assert jan["period"]["rx"] == GB and feb["period"]["rx"] == 6 * GB
    assert feb["today"]["rx"] == 4 * GB  # today and yesterday ignore the window
    mid_day = summary(owner, window(at(2027, 2, 1, 15), at(2027, 2, 2)))["servers"][0]
    assert mid_day["period"]["rx"] == 2 * GB  # the first day is counted whole
    assert summary(owner, window(at(2027, 3, 1), at(2027, 4, 1)))["servers"][0]["period"]["total"] == 0


def test_window_follows_the_offset_not_utc(owner, fixed_now):
    sid, _ = make_server(owner)
    fixed_now["now"] = at(2027, 3, 2, 12)
    put(sid, at(2027, 2, 28, 23, 0), 4 * GB)
    put(sid, at(2027, 3, 1, 0, 30), 6 * GB)  # 21:00 UTC on Feb 28
    feb = summary(owner, "%s&tz_offset_min=%d" % (window(at(2027, 2, 1), at(2027, 3, 1)), TZ))["servers"][0]
    assert feb["period"]["rx"] == 4 * GB
    utc = summary(owner, "%s&tz_offset_min=0" % window(at(2027, 2, 1, tz=timezone.utc), at(2027, 3, 1, tz=timezone.utc)))["servers"][0]
    assert utc["period"]["rx"] == 10 * GB


def test_peak_day_average_and_share(owner, fixed_now):
    a, _ = make_server(owner, "de-1")
    b, _ = make_server(owner, "nl-1", role="relay")
    for day, rx_a, rx_b in ((3, 20, 0), (2, 50, 30), (1, 10, 10)):  # Feb 3 is today
        put(a, at(2027, 2, day, 5), rx_a * GB, rx_a * GB)
        put(b, at(2027, 2, day, 5), rx_b * GB)
    put(a, at(2027, 1, 20, 23, 59), 40 * GB, 10 * GB)  # a quiet day inside 30 days, only for a
    data = summary(owner)
    by = {s["name"]: s for s in data["servers"]}
    assert by["de-1"]["peak_day"] == {"date": "2027-02-02", "rx": 50 * GB, "tx": 50 * GB, "total": 100 * GB}
    assert by["de-1"]["active_days"] == 4  # days without any traffic do not pull the average down
    assert by["de-1"]["avg_per_day"]["rx"] == (20 + 50 + 10 + 40) * GB // 4
    assert by["de-1"]["period"]["total"] == (40 + 100 + 20 + 50) * GB
    assert by["nl-1"]["role"] == "relay" and by["nl-1"]["active_days"] == 2
    assert data["fleet"]["peak_day"]["date"] == "2027-02-02" and data["fleet"]["peak_day"]["total"] == 130 * GB
    assert sum(s["share_pct"] for s in data["servers"]) == pytest.approx(100, abs=0.2)
    assert by["de-1"]["share_pct"] > by["nl-1"]["share_pct"] > 0


def test_panel_only_servers_report_their_api_role(owner, fixed_now):
    r = owner.post("/api/v1/servers", json={"name": "panel-1", "role": "panel_only"})
    assert r.status_code == 201
    assert summary(owner)["servers"][0]["role"] == "panel_only"


def test_hourly_buckets_start_on_local_hours(owner, fixed_now):
    sid, _ = make_server(owner)
    put(sid, at(2027, 2, 3, 10, 59, 59), 1)
    put(sid, at(2027, 2, 3, 11, 0, 0), 2, 20)
    put(sid, at(2027, 2, 3, 11, 59, 59), 3, 30)
    put(sid, at(2027, 2, 2, 12, 0, 0), 4)  # exactly 24 hours before the current hour: just outside 24h
    s = series(owner, "range=24h")
    assert s["bucket_s"] == 3600 and len(s["points"]) == 24
    assert s["points"][-1]["ts"] == at(2027, 2, 3, 12) and s["points"][-1]["rx"] == 0
    assert s["points"][0]["ts"] == at(2027, 2, 2, 13)
    got = {p["ts"]: (p["rx"], p["tx"]) for p in s["points"] if p["rx"] or p["tx"]}
    assert got == {at(2027, 2, 3, 10): (1, 0), at(2027, 2, 3, 11): (5, 50)}
    assert s["rx_total"] == 6 and s["tx_total"] == 50
    w = series(owner, "range=7d")
    assert len(w["points"]) == 168 and w["points"][0]["ts"] == at(2027, 1, 27, 13)
    assert {p["ts"]: p["rx"] for p in w["points"] if p["rx"]}[at(2027, 2, 2, 12)] == 4


def test_daily_buckets_follow_local_midnight(owner, fixed_now):
    sid, _ = make_server(owner)
    put(sid, at(2027, 2, 2, 23, 59, 59), 1)
    put(sid, at(2027, 2, 3, 0, 0, 0), 2)
    put(sid, at(2027, 2, 3, 3, 29, 59), 4)  # 23:59:59 UTC the day before, still the same local day
    put(sid, at(2027, 1, 5, 0, 0, 0), 8)  # first second of the 30-day range
    put(sid, at(2027, 1, 4, 23, 59, 59), 16)
    s = series(owner, "range=30d")
    assert s["bucket_s"] == 86400 and len(s["points"]) == 30
    assert s["points"][0]["ts"] == at(2027, 1, 5) and s["points"][-1]["ts"] == at(2027, 2, 3)
    assert {p["ts"]: p["rx"] for p in s["points"] if p["rx"]} == {at(2027, 1, 5): 8, at(2027, 2, 2): 1, at(2027, 2, 3): 6}
    assert len(series(owner, "range=90d")["points"]) == 90
    utc = series(owner, "range=30d&tz_offset_min=0")  # the same samples fall on other days in UTC
    by_day = {p["ts"]: p["rx"] for p in utc["points"] if p["rx"]}
    assert by_day == {at(2027, 2, 2, tz=timezone.utc): 7}  # the Jan 5 local sample is Jan 4 in UTC, outside


def test_explicit_window_picks_the_bucket_size_and_stops_at_now(owner, fixed_now):
    sid, _ = make_server(owner)
    put(sid, at(2027, 2, 1, 10), 5)
    week = series(owner, window(at(2027, 1, 28), at(2027, 2, 4)))  # 7 days: hourly, ends with the running hour
    assert week["bucket_s"] == 3600 and week["points"][0]["ts"] == at(2027, 1, 28) and week["points"][-1]["ts"] == at(2027, 2, 3, 12)
    month = series(owner, window(at(2027, 2, 1), at(2027, 3, 1)))  # a month that is not over: days up to today
    assert month["bucket_s"] == 86400 and [p["ts"] for p in month["points"]] == [at(2027, 2, d) for d in (1, 2, 3)]
    assert month["rx_total"] == 5
    future = series(owner, window(at(2027, 3, 1), at(2027, 4, 1)))
    assert future["points"] == [] and future["top_days"] == []
    year = series(owner, window(at(2026, 2, 3), at(2027, 2, 4)))  # 366 days: allowed
    assert len(year["points"]) == 366


def test_top_days_are_the_biggest_first_and_capped_at_ten(owner, fixed_now):
    sid, _ = make_server(owner)
    for n in range(12):  # day n carries n+1 GB down, 1 GB up
        put(sid, at(2027, 1, 20 + n, 6), (n + 1) * GB, GB)
    top = series(owner, "range=30d")["top_days"]
    assert len(top) == 10
    assert top[0]["date"] == "2027-01-31" and top[0]["total"] == 13 * GB and top[0]["ts"] == at(2027, 1, 31)
    assert [d["total"] for d in top] == sorted((d["total"] for d in top), reverse=True)
    assert series(owner, "range=24h")["top_days"] == []  # nothing in the last 24 hours
    assert len(series(owner, "range=7d")["top_days"]) == 4  # Jan 28 to 31 fall in the last 7 days


def test_hour_profile_averages_each_local_hour_of_day(owner, fixed_now):
    sid, _ = make_server(owner)
    put(sid, at(2027, 2, 1, 9, 15), 100, 200)
    put(sid, at(2027, 2, 2, 9, 15), 200, 400)
    put(sid, at(2027, 2, 2, 9, 45), 100)  # same hour as the line above: one bucket of 300
    put(sid, at(2027, 2, 2, 12, 5), 40)  # hour 12 has a finished sample on another day...
    put(sid, at(2027, 2, 3, 12, 10), 9999)  # ...so the running hour is left out
    put(sid, at(2027, 2, 3, 11, 10), 7)
    p = {h["hour"]: h for h in series(owner, "range=7d")["hour_profile"]}
    assert len(p) == 24
    assert p[9] == {"hour": 9, "rx": 200, "tx": 300}
    assert p[12]["rx"] == 40 and p[11]["rx"] == 7 and p[10]["rx"] == 0


def test_the_running_hour_fills_an_hour_nothing_else_covers(owner, fixed_now):
    sid, _ = make_server(owner)
    put(sid, at(2027, 2, 3, 12, 10), 90)
    p = {h["hour"]: h for h in series(owner, "range=24h")["hour_profile"]}
    assert p[12]["rx"] == 90


def test_one_server_series_only_counts_that_server(owner, fixed_now):
    a, _ = make_server(owner, "de-1")
    b, _ = make_server(owner, "nl-1")
    put(a, at(2027, 2, 3, 8), 5 * GB, GB)
    put(b, at(2027, 2, 3, 8), 7 * GB, 2 * GB)
    assert series(owner, "range=24h")["rx_total"] == 12 * GB
    one = series(owner, "range=24h&server_id=%d" % b)
    assert one["server_id"] == b and one["rx_total"] == 7 * GB and one["tx_total"] == 2 * GB
    assert owner.get("/api/v1/traffic/series?server_id=999").json()["code"] == "server.not_found"


def test_invalid_input_uses_the_error_registry(owner, fixed_now):
    r = owner.get("/api/v1/traffic/series?range=1y")
    assert r.status_code == 422 and r.json()["code"] == "traffic.range_invalid"
    for tz in (-721, 841):
        r = owner.get("/api/v1/traffic/summary?tz_offset_min=%d" % tz)
        assert r.status_code == 422 and r.json()["code"] == "traffic.tz_invalid"
        assert owner.get("/api/v1/traffic/series?tz_offset_min=%d" % tz).json()["code"] == "traffic.tz_invalid"
    assert owner.get("/api/v1/traffic/summary?tz_offset_min=-720").status_code == 200
    assert owner.get("/api/v1/traffic/summary?tz_offset_min=840").status_code == 200
    a = at(2027, 1, 1)
    for bad in ("since=%d" % a, "until=%d" % a, window(a, a), window(a + 10, a), window(a, a + 367 * 86400), window(-5, a)):
        for path in ("summary", "series"):
            r = owner.get("/api/v1/traffic/%s?%s" % (path, bad))
            assert r.status_code == 422 and r.json()["code"] == "traffic.window_invalid", (path, bad)
    assert owner.get("/api/v1/traffic/summary?" + window(a, a + 366 * 86400)).status_code == 200


def test_signed_out_is_401_and_a_read_key_is_enough(owner, fixed_now):
    token = owner.post("/api/v1/keys", json={"name": "t", "scope": "read"}).json()["token"]
    h = {"Authorization": "Bearer " + token}
    owner.post("/api/v1/auth/logout")
    assert owner.get("/api/v1/traffic/summary").status_code == 401
    assert owner.get("/api/v1/traffic/series").status_code == 401
    assert owner.get("/api/v1/traffic/summary", headers=h).status_code == 200
    assert owner.get("/api/v1/traffic/series?range=90d", headers=h).status_code == 200


def test_real_agent_reports_show_up_in_today(owner):
    from conftest import report

    _, key = make_server(owner)
    report(owner, key, net={"iface": "eth0", "rx_bytes": 1000, "tx_bytes": 1000, "rx_bps": 1, "tx_bps": 1})
    report(owner, key, net={"iface": "eth0", "rx_bytes": 51000, "tx_bytes": 11000, "rx_bps": 1, "tx_bps": 1})
    (row,) = owner.get("/api/v1/traffic/summary").json()["servers"]
    assert row["today"] == {"rx": 50000, "tx": 10000, "total": 60000}


def test_summary_and_series_can_be_limited_to_one_category(owner):
    from conftest import make_server, report

    a = owner.post("/api/v1/categories", json={"name": "الف"}).json()["id"]
    b = owner.post("/api/v1/categories", json={"name": "ب"}).json()["id"]
    one, k1 = make_server(owner, "one", "exit")
    two, k2 = make_server(owner, "two", "exit")
    three, k3 = make_server(owner, "three", "exit")
    owner.patch("/api/v1/servers/%d" % one, json={"category_id": a})
    owner.patch("/api/v1/servers/%d" % two, json={"category_id": b})
    for key, size in ((k1, 1000), (k2, 5000), (k3, 20000)):
        report(owner, key, net={"rx_bytes": 0, "tx_bytes": 0})
        report(owner, key, net={"rx_bytes": size, "tx_bytes": size // 2})
    every = owner.get("/api/v1/traffic/summary").json()
    assert {s["server_id"] for s in every["servers"]} == {one, two, three}
    only_a = owner.get("/api/v1/traffic/summary?category=%d" % a).json()
    assert [s["server_id"] for s in only_a["servers"]] == [one]
    assert only_a["fleet"]["period"]["rx"] == 1000
    none = owner.get("/api/v1/traffic/summary?category=none").json()
    assert [s["server_id"] for s in none["servers"]] == [three]
    assert owner.get("/api/v1/traffic/series?range=24h&category=%d" % b).json()["rx_total"] == 5000
    assert owner.get("/api/v1/traffic/series?range=24h").json()["rx_total"] == 26000
    bad = owner.get("/api/v1/traffic/summary?category=abc")
    assert bad.status_code == 422 and bad.json()["code"] == "traffic.category_invalid"


def test_link_traffic_can_be_limited_to_a_category(owner):
    from app.db import connect
    from conftest import make_server, report

    cat = owner.post("/api/v1/categories", json={"name": "الف"}).json()["id"]
    relay, rk = make_server(owner, "relay", "relay")
    exit_, ek = make_server(owner, "exit", "exit")
    other, ok = make_server(owner, "other", "exit")
    report(owner, rk, public_ip="203.0.113.10")
    report(owner, ek, public_ip="198.51.100.20")
    report(owner, ok, public_ip="198.51.100.30")
    owner.patch("/api/v1/servers/%d" % exit_, json={"category_id": cat})
    db = connect()
    import time
    hour = int(time.time()) // 3600 * 3600
    for ip, n in (("198.51.100.20", 10), ("198.51.100.30", 99)):
        db.execute("INSERT INTO link_traffic (server_id, peer_ip, hour, in_bytes, out_bytes) VALUES (?,?,?,?,0)", (relay, ip, hour, n))
    db.close()
    rows = owner.get("/api/v1/links/traffic?category=%d" % cat).json()["links"]
    assert [r["peer_ip"] for r in rows] == ["198.51.100.20"]
    assert len(owner.get("/api/v1/links/traffic").json()["links"]) == 2
