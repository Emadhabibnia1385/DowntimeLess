import time

from app.db import connect
from app.features.issues import service as incidents
from app.features.reports import events
from conftest import make_server, report


def _events(kind=None):
    db = connect()
    rows = db.execute("SELECT * FROM events %s ORDER BY id" % ("WHERE kind='%s'" % kind if kind else "")).fetchall()
    db.close()
    return rows


def test_server_lifecycle_events(owner):
    sid, key = make_server(owner, "de-1", "exit")
    assert [e["kind"] for e in _events()] == ["server_added"] and _events()[0]["server_id"] == sid
    owner.patch("/api/v1/servers/%d" % sid, json={"name": "de-one", "alias": "Germany"})
    renamed = _events("server_renamed")
    assert len(renamed) == 2 and "name: de-1 -> de-one" in renamed[0]["title"]
    owner.patch("/api/v1/servers/%d" % sid, json={"name": "de-one"})  # no real change: nothing logged
    assert len(_events("server_renamed")) == 2
    owner.patch("/api/v1/servers/%d" % sid, json={"acct_on": False})
    owner.patch("/api/v1/servers/%d" % sid, json={"acct_on": False})
    assert len(_events("acct_toggled")) == 1
    owner.delete("/api/v1/servers/%d" % sid)
    gone = _events("server_removed")
    assert len(gone) == 1 and gone[0]["server_id"] == sid
    got = owner.get("/api/v1/reports/changes").json()["events"]
    assert got[0]["kind"] == "server_removed" and got[0]["server"] is None  # newest first; a removed server has no name any more


def test_jobs_are_logged_when_created_and_once_when_done(owner):
    sid, key = make_server(owner, "de-1", "exit")
    job = owner.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "ping", "args": {}}).json()
    created = _events("job_created")
    assert len(created) == 1 and "ping" in created[0]["title"]
    report(owner, key)  # the agent picks the job up
    report(owner, key, jobs_done=[{"id": job["id"], "status": "ok", "result": {}}])
    report(owner, key, jobs_done=[{"id": job["id"], "status": "ok", "result": {}}])  # a repeat adds nothing
    report(owner, key, jobs_done=[{"id": 9999, "status": "ok"}])  # someone else's job id adds nothing
    done = _events("job_done")
    assert len(done) == 1 and "ping: ok" in done[0]["title"]


def test_agent_version_reboot_and_ip_changes_come_from_reports(owner):
    sid, key = make_server(owner, "de-1", "exit")
    report(owner, key, agent_version="0.2.7", public_ip="198.51.100.9", uptime_s=5000)
    assert not _events("agent_updated") and not _events("rebooted") and not _events("ip_changed")
    report(owner, key, agent_version="0.2.8", public_ip="198.51.100.9", uptime_s=5030)
    report(owner, key, agent_version="0.2.8", public_ip="198.51.100.77", uptime_s=20)
    assert [e["title"] for e in _events("agent_updated")] == ["de-1: agent 0.2.7 -> 0.2.8"]
    assert len(_events("rebooted")) == 1 and "uptime 20s" in _events("rebooted")[0]["title"]
    assert "198.51.100.9 -> 198.51.100.77" in _events("ip_changed")[0]["title"]


def test_settings_changes_are_logged_only_when_a_value_changes(owner):
    owner.put("/api/v1/settings", json={"cpu_warn": 80, "on_ram": 0})
    owner.put("/api/v1/settings", json={"cpu_warn": 80})
    ev = _events("settings_changed")
    assert len(ev) == 1 and "cpu_warn" in ev[0]["title"] and "on_ram" in ev[0]["title"]


def test_issue_open_and_close_are_logged_with_the_sweep_time(owner):
    db = connect()
    issue = {"id": "server:1:disk", "server_id": None, "server_name": "de-1", "code": "disk", "severity": "warning", "title": "t", "suggestion": "", "evidence": {}}
    now = 1_800_000_000
    incidents.record(db, 1, now, [issue])
    incidents.record(db, 1, now + 15, [issue])
    incidents.record(db, 1, now + 60, [])
    kinds = [(e["kind"], e["ts"]) for e in _events()]
    assert kinds == [("issue_opened", now), ("issue_closed", now + 15)]
    db.close()


def test_changes_filters_order_and_cap(owner):
    sid, key = make_server(owner, "de-1", "exit")
    other, _ = make_server(owner, "de-2", "exit")
    db = connect()
    now = int(time.time())
    for n in range(520):
        events.record(db, 1, "job_created", "j%d" % n, sid, ts=now - 1000 + n // 10)
    events.record(db, 1, "rebooted", "old", other, ts=now - 3 * 86400)
    db.close()
    r = owner.get("/api/v1/reports/changes").json()
    assert len(r["events"]) == 500 and r["truncated"]
    assert r["events"][0]["ts"] >= r["events"][-1]["ts"]
    only = owner.get("/api/v1/reports/changes?server_id=%d&since=%d&until=%d" % (other, now - 4 * 86400, now)).json()
    assert [e["title"] for e in only["events"]] == ["de-2 (exit)", "old"] and only["events"][1]["server"] == "de-2"
    kind = owner.get("/api/v1/reports/changes?kind=rebooted&since=%d" % (now - 5 * 86400)).json()
    assert [e["kind"] for e in kind["events"]] == ["rebooted"]
    assert owner.get("/api/v1/reports/changes?since=%d&until=%d" % (now, now - 5)).json()["code"] == "window.invalid"
    assert owner.get("/api/v1/reports/changes?since=0").json()["code"] == "window.invalid"


def test_events_older_than_180_days_are_pruned(owner):
    db = connect()
    now = int(time.time())
    events.record(db, 1, "settings_changed", "old", None, ts=now - 181 * 86400)
    events.record(db, 1, "settings_changed", "new", None, ts=now - 179 * 86400)
    events.prune(db, now)
    assert [e["title"] for e in db.execute("SELECT title FROM events")] == ["new"]
    db.close()


def test_briefing_lists_recent_changes_but_not_issue_noise(owner):
    sid, key = make_server(owner, "de-1", "exit")
    db = connect()
    events.record(db, 1, "issue_opened", "de-1: disk", sid)
    db.close()
    b = owner.get("/api/v1/reports/briefing").json()
    assert [c["kind"] for c in b["changes_24h"]] == ["server_added"] and b["issue_events_24h"] == 1
