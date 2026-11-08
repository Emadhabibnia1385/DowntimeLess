import time
from datetime import datetime, timezone

import pytest

from app.db import connect
from app.features.overview import detectors
from app.features.overview import service as overview
from conftest import make_server, report

GIB = 1024 ** 3


def codes(owner, prefix=""):
    return [i["code"] for i in owner.get("/api/v1/issues").json() if i["code"].startswith(prefix)]


def one(owner, code):
    found = [i for i in owner.get("/api/v1/issues").json() if i["code"] == code]
    assert len(found) == 1, found
    return found[0]


def feed(owner, key, n, **fields):
    for _ in range(n):
        report(owner, key, **fields)


def switch(owner, **values):
    owner.put("/api/v1/settings", json=values)


# ---- duration: cpu, conntrack, steal, load per core ---------------------------------------------

def test_cpu_must_hold_for_five_reports(owner):
    sid, key = make_server(owner)
    feed(owner, key, 4, cpu_pct=95)
    assert "cpu" not in codes(owner)
    report(owner, key, cpu_pct=95)
    issue = one(owner, "cpu")
    assert issue["severity"] == "warning" and issue["evidence"]["cpu_pct"] == 95 and issue["evidence"]["held_reports"] == 5


def test_a_dip_inside_the_window_means_the_cpu_did_not_hold(owner):
    sid, key = make_server(owner)
    feed(owner, key, 3, cpu_pct=95)
    report(owner, key, cpu_pct=20)
    feed(owner, key, 3, cpu_pct=95)
    assert "cpu" not in codes(owner)
    feed(owner, key, 2, cpu_pct=95)
    assert "cpu" in codes(owner)
    report(owner, key, cpu_pct=30)  # one calm report ends it
    assert "cpu" not in codes(owner)


def test_conntrack_needs_three_reports_and_is_critical(owner):
    sid, key = make_server(owner)
    feed(owner, key, 2, conntrack_pct=92)
    assert "conntrack" not in codes(owner)
    report(owner, key, conntrack_pct=92)
    assert one(owner, "conntrack")["severity"] == "critical"
    report(owner, key, conntrack_pct=40)
    assert "conntrack" not in codes(owner)


def test_steal_tiers_follow_the_level_it_held(owner):
    sid, key = make_server(owner, "de-1", "exit")
    feed(owner, key, 2, steal_pct=12)
    assert "steal" not in codes(owner)
    report(owner, key, steal_pct=12)
    low = one(owner, "steal")
    assert low["severity"] == "warning" and "شلوغ" in low["title"] and "شدید" not in low["title"]
    feed(owner, key, 3, steal_pct=20)
    strong = one(owner, "steal")
    assert strong["severity"] == "warning" and "شدید" in strong["title"]
    feed(owner, key, 3, steal_pct=45)
    crit = one(owner, "steal")
    assert crit["severity"] == "critical" and "بسیار" in crit["title"] and crit["evidence"]["steal_pct"] == 45
    report(owner, key, steal_pct=8)  # below the warning level: gone
    assert "steal" not in codes(owner)


def test_the_tier_is_the_lowest_of_the_last_three_reports(owner):
    sid, key = make_server(owner, "de-1", "exit")
    feed(owner, key, 1, steal_pct=12)
    feed(owner, key, 2, steal_pct=50)
    assert one(owner, "steal")["severity"] == "warning" and "شدید" not in one(owner, "steal")["title"]


def test_critical_steal_needs_a_server_that_carries_users(owner):
    sid, key = make_server(owner, "box", "other")
    feed(owner, key, 3, steal_pct=60)
    assert one(owner, "steal")["severity"] == "warning"


def test_load_per_core_needs_five_reports_at_one_per_core(owner):
    sid, key = make_server(owner)
    feed(owner, key, 4, cpu_cores=2, load1=2.6)
    assert "load_per_core" not in codes(owner)
    report(owner, key, cpu_cores=2, load1=2.6)
    issue = one(owner, "load_per_core")
    assert issue["severity"] == "warning" and issue["evidence"]["per_core"] == 1.3 and issue["evidence"]["cpu_cores"] == 2
    feed(owner, key, 5, cpu_cores=4, load1=2.6)  # same load on more cores is fine
    assert "load_per_core" not in codes(owner)
    feed(owner, key, 5, cpu_cores=2, load1=1.9)
    assert "load_per_core" not in codes(owner)


@pytest.mark.parametrize("rule, fields, n", [
    ("cpu", {"cpu_pct": 99}, 5), ("conntrack", {"conntrack_pct": 99}, 3), ("steal", {"steal_pct": 30}, 3),
    ("load_per_core", {"cpu_cores": 1, "load1": 3.0}, 5),
])
def test_the_switch_of_a_duration_rule_hides_it(owner, rule, fields, n):
    sid, key = make_server(owner)
    feed(owner, key, n, **fields)
    assert rule in codes(owner)
    switch(owner, **{"on_" + rule: 0})
    assert rule not in codes(owner)
    switch(owner, **{"on_" + rule: 1})
    assert rule in codes(owner)


# ---- events ---------------------------------------------------------------------------------------

def test_a_drop_in_uptime_is_a_reboot_that_stays_ten_minutes(owner):
    sid, key = make_server(owner, "iran-1", "relay")
    report(owner, key, uptime_s=5000)
    report(owner, key, uptime_s=5030)
    assert "rebooted" not in codes(owner)
    report(owner, key, uptime_s=45)
    issue = one(owner, "rebooted")
    assert issue["severity"] == "info" and issue["evidence"]["uptime_s"] == 45 and "چک‌لیست" in issue["suggestion"]
    report(owner, key, uptime_s=75)  # counting up again does not clear it
    assert "rebooted" in codes(owner)
    db = connect()
    db.execute("UPDATE servers SET rebooted_at=? WHERE id=?", (int(time.time()) - 590, sid))
    assert "rebooted" in codes(owner)  # still inside the ten minutes
    db.execute("UPDATE servers SET rebooted_at=? WHERE id=?", (int(time.time()) - 601, sid))
    db.close()
    assert "rebooted" not in codes(owner)
    assert detectors.REBOOT_KEEP_S == 600


def test_no_reboot_without_a_previous_uptime_and_the_switch_hides_it(owner):
    sid, key = make_server(owner)
    report(owner, key)  # an old agent without uptime
    report(owner, key, uptime_s=10)
    assert "rebooted" not in codes(owner)
    report(owner, key, uptime_s=2)
    assert "rebooted" in codes(owner)
    switch(owner, on_rebooted=0)
    assert "rebooted" not in codes(owner)


def test_ip_change_is_critical_with_the_checklist_and_not_fired_for_the_first_ip(owner):
    sid, key = make_server(owner, "iran-1", "relay")
    report(owner, key, public_ip="203.0.113.5")
    assert "ip_changed" not in codes(owner)
    report(owner, key, public_ip="203.0.113.5")
    assert "ip_changed" not in codes(owner)
    report(owner, key, public_ip="203.0.113.77")
    issue = one(owner, "ip_changed")
    assert issue["severity"] == "critical"
    assert issue["evidence"]["old_ip"] == "203.0.113.5" and issue["evidence"]["new_ip"] == "203.0.113.77"
    for part in ("GRE local", "GRE remote", "dial", "DNS", "allowlist", "nft", "اس‌اس‌اچ", "اندازه‌گیری"):
        assert part in issue["suggestion"], part
    report(owner, key, public_ip=None)  # a report without an IP keeps the known one and does not refire
    assert one(owner, "ip_changed")["evidence"]["new_ip"] == "203.0.113.77"
    db = connect()
    db.execute("UPDATE servers SET ip_changed_at=? WHERE id=?", (int(time.time()) - 86401, sid))
    db.close()
    assert "ip_changed" not in codes(owner)


def test_an_ipv6_address_is_not_an_ip_change(owner):
    sid, key = make_server(owner)
    report(owner, key, public_ip="203.0.113.5")
    report(owner, key, public_ip="2001:db8::1")
    assert "ip_changed" not in codes(owner)


def test_fewer_cores_or_less_ram_means_resized(owner):
    sid, key = make_server(owner)
    report(owner, key, cpu_cores=4, ram_total_mb=8000, ram_avail_mb=4000)
    report(owner, key, cpu_cores=4, ram_total_mb=8000, ram_avail_mb=4000)
    report(owner, key, cpu_cores=8, ram_total_mb=16000, ram_avail_mb=4000)  # growing is not a problem
    assert "resized" not in codes(owner)
    report(owner, key, cpu_cores=8, ram_total_mb=15900, ram_avail_mb=4000)  # rounding noise
    assert "resized" not in codes(owner)
    report(owner, key, cpu_cores=4, ram_total_mb=15900, ram_avail_mb=4000)
    issue = one(owner, "resized")
    assert issue["severity"] == "warning" and (issue["evidence"]["cpu_cores_before"], issue["evidence"]["cpu_cores_now"]) == (8, 4)
    assert "ram_total_mb_before" not in issue["evidence"]
    db = connect()
    db.execute("UPDATE servers SET resized_at=? WHERE id=?", (int(time.time()) - 86401, sid))
    db.close()
    assert "resized" not in codes(owner)
    report(owner, key, cpu_cores=4, ram_total_mb=4000, ram_avail_mb=1000)
    assert (one(owner, "resized")["evidence"]["ram_total_mb_before"], one(owner, "resized")["evidence"]["ram_total_mb_now"]) == (15900, 4000)
    switch(owner, on_resized=0)
    assert "resized" not in codes(owner)


# ---- cause of a failing path ---------------------------------------------------------------------

@pytest.fixture
def fast_pings(monkeypatch):
    monkeypatch.setattr(overview, "PING_MIN_SAMPLES", 1)


def fleet(owner, exits, relays):
    """exits: {name: ip}; relays: [{target ip: loss}], one dict per relay named iran-1.."""
    for name, ip in exits.items():
        _, k = make_server(owner, name, "exit")
        report(owner, k, public_ip=ip)
    for n, losses in enumerate(relays, 1):
        _, k = make_server(owner, "iran-%d" % n, "relay")
        report(owner, k, public_ip="203.0.113.%d" % n, ping=[{"target": ip, "loss_pct": loss, "rtt_ms": 90} for ip, loss in losses.items()])


def test_an_online_exit_failing_from_every_relay_is_blacklisted(owner, fast_pings):
    fleet(owner, {"nl-1": "198.51.100.2"}, [{"198.51.100.2": 100}, {"198.51.100.2": 100}])
    issue = one(owner, "blacklisted")
    assert issue["severity"] == "critical" and issue["title"] == "IP از داخل ایران مسدود شده" and issue["server_name"] == "nl-1"
    assert issue["evidence"]["relays"] == ["iran-1", "iran-2"]
    assert codes(owner, "ping:") == []  # the cause replaces the plain loss issue


def test_blacklisted_needs_two_relays_agreeing_and_an_online_server(owner, fast_pings):
    fleet(owner, {"nl-1": "198.51.100.2"}, [{"198.51.100.2": 100}])
    assert "blacklisted" not in codes(owner) and codes(owner, "ping:")  # one relay stays the unconfirmed info
    sid, key = make_server(owner, "iran-9", "relay")
    report(owner, key, public_ip="203.0.113.9", ping=[{"target": "198.51.100.2", "loss_pct": 100, "rtt_ms": None}])
    assert "blacklisted" in codes(owner)
    db = connect()
    db.execute("UPDATE servers SET last_seen=? WHERE name='nl-1'", (int(time.time()) - 3600,))
    db.close()
    found = codes(owner)
    assert "blacklisted" not in found and "offline" in found and "ping:198.51.100.2" in found  # silent agent: an outage


def test_partial_loss_from_all_relays_stays_a_plain_ping_issue(owner, fast_pings):
    fleet(owner, {"nl-1": "198.51.100.2"}, [{"198.51.100.2": 30}, {"198.51.100.2": 30}])
    assert "blacklisted" not in codes(owner) and codes(owner, "ping:") == ["ping:198.51.100.2"]


def test_exactly_one_failing_relay_is_an_egress_filter_on_that_relay(owner, fast_pings):
    fleet(owner, {"nl-1": "198.51.100.2"}, [{"198.51.100.2": 100}, {"198.51.100.2": 0}, {"198.51.100.2": 0}])
    issue = one(owner, "relay_egress")
    assert issue["severity"] == "warning" and issue["server_name"] == "iran-1"
    assert issue["evidence"]["target"] == "nl-1" and issue["evidence"]["reached_by"] == ["iran-2", "iran-3"]
    assert "blacklisted" not in codes(owner)


def test_a_relay_failing_to_several_servers_is_one_filtered_relay(owner, fast_pings):
    both = {"198.51.100.2": 100, "198.51.100.3": 100}
    fleet(owner, {"nl-1": "198.51.100.2", "de-1": "198.51.100.3"}, [both, {"198.51.100.2": 0, "198.51.100.3": 0}])
    issue = one(owner, "relay_filtered")
    assert issue["server_name"] == "iran-1" and issue["evidence"]["targets"] == ["de-1", "nl-1"] and issue["evidence"]["count"] == 2
    assert "relay_egress" not in codes(owner)


def test_the_cause_switches_hide_their_issue_and_bring_back_the_plain_one(owner, fast_pings):
    fleet(owner, {"nl-1": "198.51.100.2"}, [{"198.51.100.2": 100}, {"198.51.100.2": 100}])
    switch(owner, on_blacklisted=0)
    assert "blacklisted" not in codes(owner) and codes(owner, "ping:") == ["ping:198.51.100.2"]
    switch(owner, on_blacklisted=1, on_ping=0)
    assert "blacklisted" in codes(owner)


def test_egress_and_filter_switches(owner, fast_pings):
    both = {"198.51.100.2": 100, "198.51.100.3": 100}
    fleet(owner, {"nl-1": "198.51.100.2", "de-1": "198.51.100.3"}, [both, {"198.51.100.2": 0, "198.51.100.3": 0}])
    switch(owner, on_relay_filtered=0)
    assert "relay_filtered" not in codes(owner) and "relay_egress" not in codes(owner)


# ---- quota ---------------------------------------------------------------------------------------

def put_traffic(sid, now, hours, per_hour_out, per_hour_in=0):
    db = connect()
    for k in range(hours):
        db.execute("INSERT INTO metrics (server_id, ts, tx_delta, rx_delta) VALUES (?,?,?,?)", (sid, now - k * 3600 - 60, per_hour_out, per_hour_in))
    db.close()


def reset_day_ten_days_ago():
    return datetime.fromtimestamp(time.time() - 10 * 86400, timezone.utc).day


def quota_server(owner, name="iran-1", role="relay", quota=100, **traffic):
    sid, key = make_server(owner, name, role)
    report(owner, key)
    r = owner.patch("/api/v1/servers/%d" % sid, json={"quota_gb": quota, "quota_reset_day": reset_day_ten_days_ago()})
    assert r.status_code == 200
    return sid


def test_quota_fields_roundtrip_validate_and_clear(owner):
    sid, _ = make_server(owner)
    r = owner.patch("/api/v1/servers/%d" % sid, json={"quota_gb": 500, "quota_reset_day": 15}).json()
    assert r["quota_gb"] == 500 and r["quota_reset_day"] == 15
    assert owner.get("/api/v1/servers/%d" % sid).json()["quota_gb"] == 500
    assert owner.patch("/api/v1/servers/%d" % sid, json={"alias": "x"}).json()["quota_gb"] == 500  # left out: kept
    for bad in ({"quota_reset_day": 0}, {"quota_reset_day": 32}, {"quota_gb": 0}, {"quota_gb": -5}):
        assert owner.patch("/api/v1/servers/%d" % sid, json=bad).status_code == 422
    r = owner.patch("/api/v1/servers/%d" % sid, json={"quota_gb": None, "quota_reset_day": None}).json()
    assert r["quota_gb"] is None and r["quota_reset_day"] is None


def test_quota_is_critical_when_it_runs_out_within_two_days(owner):
    sid = quota_server(owner)
    put_traffic(sid, int(time.time()), 72, 25 * GIB // 24)  # 25 GiB a day for three days: 75 used, 1 day left
    issue = one(owner, "quota")
    assert issue["severity"] == "critical" and issue["server_name"] == "iran-1"
    ev = issue["evidence"]
    assert ev["quota_gb"] == 100 and 74 <= ev["used_gb"] <= 76 and 24 <= ev["per_day_gb"] <= 26 and 0.9 <= ev["days_left"] <= 1.1
    assert ev["basis"] == "out" and ev["resets_in_days"] > 5


def test_quota_warns_inside_a_week_and_is_silent_beyond_it(owner):
    sid = quota_server(owner, quota=100)
    put_traffic(sid, int(time.time()), 72, 10 * GIB // 24)  # 30 used, 10 a day: 7 days left
    assert "quota" not in codes(owner)
    owner.patch("/api/v1/servers/%d" % sid, json={"quota_gb": 80})  # 50 left at 10 a day: 5 days
    assert one(owner, "quota")["severity"] == "warning"
    owner.patch("/api/v1/servers/%d" % sid, json={"quota_gb": 500})
    assert "quota" not in codes(owner)


def test_quota_above_one_hundred_percent_is_critical_and_needs_no_rate(owner):
    sid = quota_server(owner, quota=10)
    put_traffic(sid, int(time.time()) - 5 * 86400, 1, 11 * GIB)  # one old spike, nothing recently
    issue = one(owner, "quota")
    assert issue["severity"] == "critical" and issue["evidence"]["used_pct"] >= 100 and issue["evidence"]["days_left"] == 0


def test_a_quota_that_resets_before_it_runs_out_is_not_an_alert(owner):
    sid, key = make_server(owner)
    report(owner, key)
    tomorrow = datetime.fromtimestamp(time.time() + 86400, timezone.utc).day
    owner.patch("/api/v1/servers/%d" % sid, json={"quota_gb": 100, "quota_reset_day": tomorrow})
    put_traffic(sid, int(time.time()), 72, 5 * GIB // 24)
    assert "quota" not in codes(owner)


def test_quota_basis_counts_incoming_bytes_when_asked(owner):
    sid = quota_server(owner, quota=100)
    put_traffic(sid, int(time.time()), 72, 5 * GIB // 24, 5 * GIB // 24)  # 5 out + 5 in a day
    assert "quota" not in codes(owner)
    switch(owner, quota_basis=1)
    owner.patch("/api/v1/servers/%d" % sid, json={"quota_gb": 60})  # 30 used both ways, 10 a day: 3 days
    issue = one(owner, "quota")
    assert issue["evidence"]["basis"] == "both" and issue["severity"] == "warning"


def test_no_quota_set_means_no_forecast_and_the_switch_hides_it(owner):
    sid, key = make_server(owner)
    report(owner, key)
    put_traffic(sid, int(time.time()), 72, 500 * GIB // 24)
    assert "quota" not in codes(owner)
    owner.patch("/api/v1/servers/%d" % sid, json={"quota_gb": 100, "quota_reset_day": reset_day_ten_days_ago()})
    assert "quota" in codes(owner)
    switch(owner, on_quota=0)
    assert "quota" not in codes(owner)


def test_two_relays_running_out_within_48_hours_are_a_pair(owner):
    a = quota_server(owner, "iran-1")
    b = quota_server(owner, "iran-2")
    c = quota_server(owner, "iran-3")
    put_traffic(a, int(time.time()), 72, 15 * GIB // 24)  # 45 used, 15 a day: 3.7 days
    put_traffic(b, int(time.time()), 72, 12 * GIB // 24)  # 36 used, 12 a day: 5.3 days
    put_traffic(c, int(time.time()), 72, 3 * GIB // 24)  # far from empty
    pair = one(owner, "quota_pair")
    assert pair["severity"] == "warning" and pair["server_id"] is None
    assert pair["evidence"]["relays"] == ["iran-1", "iran-2"] and pair["evidence"]["gap_hours"] <= 48
    switch(owner, on_quota_pair=0)
    assert "quota_pair" not in codes(owner) and codes(owner).count("quota") == 2


def test_relays_more_than_48_hours_apart_or_other_roles_are_not_a_pair():
    def s(i, role="relay"):
        return {"id": i, "alias": "", "name": "r%d" % i, "role": role}

    def f(days):
        return {"days_left": days, "runs_out": True}

    assert detectors.quota_pairs([(s(1), f(1.0)), (s(2), f(3.5))]) == []
    assert detectors.quota_pairs([(s(1), f(1.0)), (s(2, "exit"), f(1.5))]) == []
    assert detectors.quota_pairs([(s(1), f(1.0)), (s(2), {"days_left": 1.2, "runs_out": False})]) == []
    # everyone in a group runs out within 48 hours of its first member
    groups = detectors.quota_pairs([(s(1), f(1.0)), (s(2), f(2.5)), (s(3), f(2.9)), (s(4), f(4.0)), (s(5), f(5.5))])
    assert [g["evidence"]["relays"] for g in groups] == [["r1", "r2", "r3"], ["r4", "r5"]]


def test_the_billing_period_follows_the_reset_day():
    ts = lambda y, m, d, h=12: int(datetime(y, m, d, h, tzinfo=timezone.utc).timestamp())  # noqa: E731
    assert detectors.quota_period(ts(2026, 11, 20), 5) == (ts(2026, 11, 5, 0), ts(2026, 12, 5, 0))
    assert detectors.quota_period(ts(2026, 11, 3), 5) == (ts(2026, 10, 5, 0), ts(2026, 11, 5, 0))
    assert detectors.quota_period(ts(2026, 1, 2), 5) == (ts(2025, 12, 5, 0), ts(2026, 1, 5, 0))
    assert detectors.quota_period(ts(2026, 12, 20), 5) == (ts(2026, 12, 5, 0), ts(2027, 1, 5, 0))
    assert detectors.quota_period(ts(2026, 2, 28, 12), 31) == (ts(2026, 2, 28, 0), ts(2026, 3, 31, 0))  # short month clamps


# ---- free upload: count_upload off means only download (rx) counts ----------------------------------

def test_count_upload_defaults_on_and_patch_toggles_it(owner):
    sid, _ = make_server(owner)
    assert owner.get("/api/v1/servers/%d" % sid).json()["count_upload"] is True
    assert owner.patch("/api/v1/servers/%d" % sid, json={"count_upload": False}).json()["count_upload"] is False
    assert owner.patch("/api/v1/servers/%d" % sid, json={"alias": "x"}).json()["count_upload"] is False  # untouched by other edits
    assert owner.patch("/api/v1/servers/%d" % sid, json={"count_upload": True}).json()["count_upload"] is True
    assert [s["count_upload"] for s in owner.get("/api/v1/servers").json()] == [True]


@pytest.mark.parametrize("basis", [0, 1])
def test_free_upload_counts_download_only_under_both_bases(owner, basis):
    sid = quota_server(owner, quota=100)
    put_traffic(sid, int(time.time()), 72, 20 * GIB // 24, 1 * GIB // 24)  # 60 up (out) but only 3 down in
    switch(owner, quota_basis=basis)
    owner.patch("/api/v1/servers/%d" % sid, json={"count_upload": False})
    assert "quota" not in codes(owner)  # 3 GiB of 100, 1 a day: nowhere near
    owner.patch("/api/v1/servers/%d" % sid, json={"quota_gb": 5})  # 3 used of 5 at 1 a day: 2 days left
    issue = one(owner, "quota")
    ev = issue["evidence"]
    assert ev["basis"] == "download" and ev["used_gb"] == 3.0 and ev["per_day_gb"] == 1.0
    assert "فقط دانلود" in issue["suggestion"]
    owner.patch("/api/v1/servers/%d" % sid, json={"count_upload": True})
    assert one(owner, "quota")["evidence"]["basis"] == ("both" if basis else "out")


def test_free_upload_server_drops_out_of_the_quota_pair(owner):
    a = quota_server(owner, "iran-1")
    b = quota_server(owner, "iran-2")
    for sid in (a, b):
        put_traffic(sid, int(time.time()), 72, 15 * GIB // 24, 0)
    assert one(owner, "quota_pair")
    owner.patch("/api/v1/servers/%d" % a, json={"count_upload": False})  # only download counts, and there is none
    assert "quota_pair" not in codes(owner) and codes(owner).count("quota") == 1


def test_forecast_reads_the_count_upload_column_directly():
    th = {"quota_basis": 1}
    assert detectors.quota_counted({"count_upload": 0}, th) == ("rx_delta", "download")
    assert detectors.quota_counted({"count_upload": 1}, th) == ("rx_delta+tx_delta", "both")
    assert detectors.quota_counted({"count_upload": 1}, {"quota_basis": 0}) == ("tx_delta", "out")
