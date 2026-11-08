import json
import time

from app.db import connect
from app.features.issues import service as svc
from conftest import make_server, report

NOW = 1_800_000_000


def issue(key="server:1:disk", severity="warning", title="دیسک", **evidence):
    return {"id": key, "server_id": None, "server_name": "de-1", "code": key.split(":")[-1], "severity": severity,
            "title": title, "suggestion": "", "evidence": evidence}


def put(db, key, opened, closed=None, severity="warning", server_id=None, last_seen=None, title="t"):
    db.execute(
        "INSERT INTO incidents (key, code, server_id, server_name, severity, title, evidence, opened_at, last_seen, closed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (key, key.split(":")[-1], server_id, "de-1", severity, title, json.dumps({"k": key}), opened, last_seen or closed or opened, closed),
    )


def rows(db):
    return db.execute("SELECT * FROM incidents ORDER BY id").fetchall()


def test_lifecycle_open_update_close(owner):
    db = connect()
    svc.record(db, 1, NOW, [issue(disk_pct=91)])
    (r,) = rows(db)
    assert (r["key"], r["opened_at"], r["last_seen"], r["closed_at"], r["severity"]) == ("server:1:disk", NOW, NOW, None, "warning")
    svc.record(db, 1, NOW + 15, [issue(severity="critical", title="دیسک پر", disk_pct=97)])
    (r,) = rows(db)
    assert r["last_seen"] == NOW + 15 and r["severity"] == "critical" and r["title"] == "دیسک پر"
    assert json.loads(r["evidence"]) == {"disk_pct": 97}
    svc.record(db, 1, NOW + 30, [issue(severity="warning", disk_pct=85)])  # severity only goes up
    assert rows(db)[0]["severity"] == "critical" and len(rows(db)) == 1
    svc.record(db, 1, NOW + 45, [])
    assert rows(db)[0]["closed_at"] is None  # absent for one sweep: still open
    svc.record(db, 1, NOW + 60, [])
    (r,) = rows(db)
    assert r["closed_at"] == NOW + 30  # ends at the last sweep that saw it
    svc.record(db, 1, NOW + 75, [issue()])
    assert len(rows(db)) == 2 and rows(db)[1]["closed_at"] is None  # a new occurrence, not a reopen
    db.close()


def test_a_blink_of_one_sweep_is_one_incident(owner):
    db = connect()
    svc.record(db, 1, NOW, [issue()])
    svc.record(db, 1, NOW + 15, [])
    svc.record(db, 1, NOW + 30 - 1, [issue()])
    svc.record(db, 1, NOW + 45, [issue()])
    (r,) = rows(db)
    assert r["closed_at"] is None and r["last_seen"] == NOW + 45
    db.close()


def test_info_issues_are_recorded_and_issues_are_independent(owner):
    db = connect()
    svc.record(db, 1, NOW, [issue("server:1:agent_missing", "info"), issue("server:1:reboot_required", "info"), issue()])
    assert {r["key"] for r in rows(db)} == {"server:1:agent_missing", "server:1:reboot_required", "server:1:disk"}
    svc.record(db, 1, NOW + 15, [issue("server:1:reboot_required", "info"), issue()])
    svc.record(db, 1, NOW + 50, [issue()])
    closed = {r["key"] for r in rows(db) if r["closed_at"]}
    assert closed == {"server:1:agent_missing", "server:1:reboot_required"}
    db.close()


def test_incidents_of_a_deleted_server_close_at_once(owner):
    sid, _ = make_server(owner)
    db = connect()
    put(db, "server:%d:disk" % sid, NOW - 100, last_seen=NOW - 5, server_id=sid)
    put(db, "server:999:disk", NOW - 100, last_seen=NOW - 5, server_id=999)
    put(db, "ssl:x", NOW - 100, last_seen=NOW - 5, server_id=None)
    svc.record(db, 1, NOW, [])
    state = {r["key"]: r["closed_at"] for r in rows(db)}
    assert state["server:999:disk"] == NOW - 5
    assert state["server:%d:disk" % sid] is None and state["ssl:x"] is None  # still inside the grace period
    db.close()


def test_pruning_drops_only_old_closed_incidents(owner):
    db = connect()
    put(db, "old", NOW - 100 * 86400, NOW - 95 * 86400)
    put(db, "recent", NOW - 80 * 86400, NOW - 79 * 86400)
    put(db, "open-old", NOW - 120 * 86400, None, last_seen=NOW)
    svc.record(db, 1, NOW, [issue("open-old")])
    assert {r["key"] for r in rows(db)} == {"recent", "open-old"}
    db.close()


def test_history_counts_occurrences_and_clips_time_to_the_range(owner):
    now = int(time.time())
    db = connect()
    put(db, "server:1:disk", now - 2 * 86400, now - 2 * 86400 + 600, "warning")
    put(db, "server:1:disk", now - 3600, now - 1800, "critical")
    put(db, "server:1:disk", now - 600, None, "warning", last_seen=now)
    put(db, "server:1:cpu", now - 20 * 86400, now - 20 * 86400 + 100, "warning")  # only in the 30d range
    put(db, "server:1:ram", now - 40 * 86400, now - 31 * 86400, "warning")  # entirely outside 30d
    put(db, "server:1:ping", now - 8 * 86400, now - 7 * 86400 + 3600, "warning")  # straddles the 7d edge
    db.close()
    day = owner.get("/api/v1/issues/history?range=24h").json()
    assert day["range"] == "24h" and day["since"] == pytest_approx(now - 86400)
    (disk,) = day["summary"]
    assert disk["key"] == "server:1:disk" and disk["occurrences"] == 2 and disk["severity"] == "critical"
    assert disk["active_now"] is True and disk["flapping"] is False
    assert abs(disk["total_s"] - (1800 + 600)) <= 3
    assert day["totals"] == {"occurrences": 2, "issues": 1, "active_now": 1, "critical": 1}
    assert [i["closed_at"] is None for i in day["incidents"]] == [True, False]  # newest first
    week = owner.get("/api/v1/issues/history?range=7d").json()
    by = {s["key"]: s for s in week["summary"]}
    assert by["server:1:disk"]["occurrences"] == 3 and by["server:1:disk"]["flapping"] is True
    assert abs(by["server:1:disk"]["total_s"] - (600 + 1800 + 600)) <= 3
    assert by["server:1:ping"]["occurrences"] == 1 and abs(by["server:1:ping"]["total_s"] - 3600) <= 3  # clipped
    assert "server:1:cpu" not in by and "server:1:ram" not in by
    assert week["summary"][0]["key"] == "server:1:disk"  # most occurrences first
    month = owner.get("/api/v1/issues/history?range=30d").json()
    keys = {s["key"] for s in month["summary"]}
    assert "server:1:cpu" in keys and "server:1:ram" not in keys
    cpu = next(s for s in month["summary"] if s["key"] == "server:1:cpu")
    assert cpu["active_now"] is False and cpu["evidence"] == {"k": "server:1:cpu"}
    ping = next(s for s in month["summary"] if s["key"] == "server:1:ping")
    assert abs(ping["total_s"] - 90000) <= 3  # unclipped inside 30d: 25 hours


def pytest_approx(value):
    class Near:
        def __eq__(self, other):
            return abs(other - value) <= 3

    return Near()


def test_summary_order_and_incident_limit(owner):
    now = int(time.time())
    db = connect()
    for n in range(4):
        put(db, "server:1:a", now - 3000 + n * 100, now - 3000 + n * 100 + 50, "warning")
    for n in range(2):
        put(db, "server:1:b", now - 2000 + n * 100, now - 2000 + n * 100 + 50, "critical")
    for n in range(2):
        put(db, "server:1:c", now - 1000 + n * 100, now - 1000 + n * 100 + 50, "info")
    for n in range(300):
        put(db, "server:1:many", now - 4000 - n, now - 4000 - n + 1, "info")
    db.close()
    data = owner.get("/api/v1/issues/history?range=24h").json()
    assert [s["key"] for s in data["summary"][:3]] == ["server:1:many", "server:1:a", "server:1:b"]
    assert len(data["incidents"]) == 300 and data["totals"]["occurrences"] == 308
    assert data["incidents"][0]["opened_at"] >= data["incidents"][-1]["opened_at"]


def test_invalid_range_and_permissions(owner):
    assert owner.get("/api/v1/issues/history?range=1y").status_code == 422
    assert owner.get("/api/v1/issues/history?range=1y").json()["code"] == "range.invalid"
    token = owner.post("/api/v1/keys", json={"name": "t", "scope": "read"}).json()["token"]
    h = {"Authorization": "Bearer " + token}
    owner.post("/api/v1/auth/logout")
    assert owner.get("/api/v1/issues/history", headers=h).status_code == 200  # a read key is a viewer
    assert owner.get("/api/v1/issues/history").status_code == 401


def test_current_issues_carry_their_recent_count_and_the_sweep_records_them(owner, tg):
    from app.monitor import sweep

    sid, key = make_server(owner)
    report(owner, key, disk_used_gb=96)
    assert owner.get("/api/v1/issues").json()[0]["recent_24h"] == 0  # nothing recorded yet
    sweep(tg)
    disk = next(i for i in owner.get("/api/v1/issues").json() if i["code"] == "disk")
    assert disk["recent_24h"] == 1
    db = connect()
    put(db, disk["id"], int(time.time()) - 7200, int(time.time()) - 7000)
    db.close()
    disk = next(i for i in owner.get("/api/v1/issues").json() if i["code"] == "disk")
    assert disk["recent_24h"] == 2
    hist = owner.get("/api/v1/issues/history").json()
    assert hist["totals"]["active_now"] >= 1 and hist["summary"][0]["occurrences"] == 2


def test_a_failing_recorder_never_stops_the_rest_of_the_sweep(owner, tg, monkeypatch):
    from app import monitor

    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(monitor.incidents_svc, "record", boom)
    sid, key = make_server(owner)
    report(owner, key)
    db = connect()
    db.execute("UPDATE servers SET last_seen=?", (int(time.time()) - 1000,))
    db.close()
    monitor.sweep(tg)
    assert any("گزارش نمی‌دهد" in m[1] for m in tg.sent)
