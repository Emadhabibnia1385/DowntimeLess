"""Acknowledged issues: listed but quiet (not counted, no Telegram) until resolved, expired, escalated or undone."""
import time

import pytest

from app import alerts, monitor
from app.db import connect
from app.features.issues import acks
from app.features.issues import service as svc
from app.features.ssl import service as ssl_svc
from conftest import make_server, report
from test_ws_roles import team  # noqa: F401  (fixture)
from ws_world import build

NOW = 1_800_000_000


def issue(code="cpu", key=None, severity="warning", name="de-1"):
    return {"id": key or "server:1:" + code, "server_id": None, "server_name": name, "code": code, "severity": severity,
            "title": "مصرف CPU بالاست", "suggestion": "یک پردازش را ببینید.", "evidence": {"cpu_pct": 97}}


def step(db, tg, found, now):
    """One monitor sweep over a made-up list of issues: incident log, acks, then Telegram."""
    alerts.dispatch(db, tg, 1, acks.screen(db, 1, found, svc.record(db, 1, now, found), now), now)


def sent(tg):
    return [m[1] for m in tg.sent if m[0] == 111 and "ورود" not in m[1]]


def to_admins(owner):
    assert owner.put("/api/v1/telegram/routes", json={"cpu": "admins"}).status_code == 200


def ack_row(db, key, mode="always", severity="warning", until=None, ws=1):
    db.execute("INSERT INTO issue_acks (workspace_id, key, mode, until, severity, note, created_at) VALUES (?,?,?,?,?,'',?)",
               (ws, key, mode, until, severity, NOW))


def ack_keys(db, ws=1):
    return [r[0] for r in db.execute("SELECT key FROM issue_acks WHERE workspace_id=?", (ws,))]


def disk_server(owner, name="de-1", used=90):
    sid, key = make_server(owner, name)
    report(owner, key, disk_used_gb=used)
    return sid, key, "server:%d:disk" % sid


def by_id(client, key):
    return next(i for i in client.get("/api/v1/issues").json() if i["id"] == key)


def kinds(client, kind):
    return client.get("/api/v1/reports/changes?kind=" + kind).json()["events"]


# ---- API and modes --------------------------------------------------------------------------------

def test_each_mode_sets_its_end_and_the_issue_is_listed_quiet(owner):
    _, _, key = disk_server(owner)
    assert by_id(owner, key)["acked"] is False
    assert owner.get("/api/v1/overview").json()["issues_warning"] == 1
    for mode, span in (("24h", 86400), ("7d", 7 * 86400), ("always", None), ("until_resolved", None)):
        before = int(time.time())
        r = owner.post("/api/v1/issues/ack", json={"key": key, "mode": mode, "note": " خودم می‌دانم "})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["mode"] == mode and body["note"] == "خودم می‌دانم" and body["severity"] == "warning"
        if span is None:
            assert body["until"] is None
        else:
            assert before + span <= body["until"] <= int(time.time()) + span
    got = by_id(owner, key)
    assert got["acked"] is True and got["ack_mode"] == "until_resolved" and got["acked_by"] == "Emad"
    assert got["ack_note"] == "خودم می‌دانم" and got["acked_until"] is None
    assert owner.get("/api/v1/overview").json()["issues_warning"] == 0  # listed, not counted
    acked = kinds(owner, "issue_acked")
    assert len(acked) == 4 and acked[0]["detail"]["mode"] == "until_resolved" and acked[0]["detail"]["user_id"]
    assert owner.delete("/api/v1/issues/ack?key=" + key).status_code == 204
    assert by_id(owner, key)["acked"] is False and owner.get("/api/v1/overview").json()["issues_warning"] == 1
    assert kinds(owner, "issue_unacked")[0]["detail"]["reason"] == "undo"
    assert owner.delete("/api/v1/issues/ack?key=" + key).json()["code"] == "ack.not_found"


def test_only_a_current_issue_and_a_known_mode_can_be_acknowledged(owner):
    _, _, key = disk_server(owner)
    r = owner.post("/api/v1/issues/ack", json={"key": "server:999:cpu", "mode": "24h"})
    assert r.status_code == 404 and r.json()["code"] == "issue.not_found"
    assert owner.post("/api/v1/issues/ack", json={"key": key, "mode": "forever"}).status_code == 422
    assert owner.post("/api/v1/issues/ack", json={"key": key, "mode": "24h", "note": "x" * 201}).status_code == 422
    assert owner.post("/api/v1/issues/ack", json={"key": key}).json()["mode"] == "until_resolved"  # the default


def test_an_expired_ack_makes_the_issue_loud_again(owner):
    _, _, key = disk_server(owner)
    owner.post("/api/v1/issues/ack", json={"key": key, "mode": "24h"})
    db = connect()
    db.execute("UPDATE issue_acks SET until=? WHERE key=?", (int(time.time()) - 1, key))
    db.close()
    assert by_id(owner, key)["acked"] is False
    assert owner.get("/api/v1/overview").json()["issues_warning"] == 1


def test_a_worse_severity_is_never_hidden(owner):
    sid, agent, key = disk_server(owner)
    owner.post("/api/v1/issues/ack", json={"key": key, "mode": "always"})
    assert by_id(owner, key)["acked"] is True
    report(owner, agent, disk_used_gb=97)  # warning -> critical
    got = by_id(owner, key)
    assert got["severity"] == "critical" and got["acked"] is False
    assert owner.get("/api/v1/overview").json()["issues_critical"] == 1


# ---- Telegram ---------------------------------------------------------------------------------------

def test_an_acked_issue_opens_and_closes_silently_and_until_resolved_ends_with_it(owner, tg):
    to_admins(owner)
    db = connect()
    ack_row(db, "server:1:cpu", "until_resolved")
    step(db, tg, [issue()], NOW)
    assert sent(tg) == []
    assert db.execute("SELECT COUNT(*) FROM incidents WHERE key='server:1:cpu'").fetchone()[0] == 1  # still recorded
    step(db, tg, [], NOW + 15)
    assert ack_keys(db) == ["server:1:cpu"]  # a blink inside the grace period is the same incident
    step(db, tg, [], NOW + 100)
    assert sent(tg) == [] and ack_keys(db) == []
    step(db, tg, [issue()], NOW + 200)  # the next time it comes back it alerts as usual
    assert len(sent(tg)) == 1 and sent(tg)[0].startswith("🟠")
    db.close()


def test_no_recovery_message_for_an_issue_acknowledged_after_its_alert(owner, tg):
    to_admins(owner)
    db = connect()
    step(db, tg, [issue()], NOW)
    assert len(sent(tg)) == 1
    ack_row(db, "server:1:cpu", "always")
    step(db, tg, [], NOW + 100)
    assert len(sent(tg)) == 1
    assert ack_keys(db) == ["server:1:cpu"]  # 'always' outlives the incident
    db.close()


def test_an_acked_flapping_issue_says_nothing(owner, tg):
    to_admins(owner)
    db = connect()
    ack_row(db, "server:1:cpu", "always")
    for k in range(5):
        step(db, tg, [issue()], NOW + k * 200)
        step(db, tg, [], NOW + k * 200 + 100)
    assert sent(tg) == []
    assert db.execute("SELECT COUNT(*) FROM flapping WHERE workspace_id=1").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM incidents WHERE key='server:1:cpu'").fetchone()[0] == 5
    db.close()


def test_escalation_ends_the_ack_and_alerts_once(owner, tg):
    db = connect()
    ack_row(db, "server:1:disk", "always", "warning")
    step(db, tg, [issue("disk")], NOW)
    assert sent(tg) == []
    step(db, tg, [issue("disk", severity="critical")], NOW + 15)
    assert len(sent(tg)) == 1 and sent(tg)[0].startswith("🔴")
    assert ack_keys(db) == []
    reason = db.execute("SELECT detail FROM events WHERE kind='issue_unacked'").fetchone()[0]
    assert '"escalated"' in reason
    step(db, tg, [issue("disk", severity="critical")], NOW + 30)
    assert len(sent(tg)) == 1
    db.close()


def test_a_time_ack_expires_and_the_open_issue_alerts(owner, tg):
    to_admins(owner)
    db = connect()
    ack_row(db, "server:1:cpu", "24h", until=NOW + 50)
    step(db, tg, [issue()], NOW)
    step(db, tg, [issue()], NOW + 30)
    assert sent(tg) == []
    step(db, tg, [issue()], NOW + 60)
    assert len(sent(tg)) == 1 and sent(tg)[0].startswith("🟠")
    assert ack_keys(db) == []
    db.close()


def test_the_monitor_keeps_an_acked_offline_server_quiet(owner, tg):
    sid, agent = make_server(owner, "ir-1", "relay")
    report(owner, agent)
    db = connect()
    db.execute("UPDATE servers SET last_seen=? WHERE id=?", (int(time.time()) - 1000, sid))
    key = "server:%d:offline" % sid
    assert owner.post("/api/v1/issues/ack", json={"key": key, "mode": "always"}).status_code == 200
    monitor.sweep_workspace(db, tg, 1)
    monitor.sweep_workspace(db, tg, 1)
    assert not [m for m in sent(tg) if "گزارش نمی‌دهد" in m]
    assert db.execute("SELECT offline_notified FROM servers WHERE id=?", (sid,)).fetchone()[0] == 0
    owner.delete("/api/v1/issues/ack?key=" + key)
    monitor.sweep_workspace(db, tg, 1)
    assert len([m for m in sent(tg) if "گزارش نمی‌دهد" in m]) == 1
    db.close()


def test_the_monitor_does_not_send_a_recovery_for_an_acked_offline_server(owner, tg):
    sid, agent = make_server(owner, "ir-1", "relay")
    report(owner, agent)
    db = connect()
    db.execute("UPDATE servers SET last_seen=? WHERE id=?", (int(time.time()) - 1000, sid))
    monitor.sweep_workspace(db, tg, 1)
    assert len([m for m in sent(tg) if "گزارش نمی‌دهد" in m]) == 1
    owner.post("/api/v1/issues/ack", json={"key": "server:%d:offline" % sid, "mode": "until_resolved"})
    report(owner, agent)  # back online
    monitor.sweep_workspace(db, tg, 1)
    assert not [m for m in sent(tg) if "دوباره آنلاین" in m]
    assert db.execute("SELECT offline_notified FROM servers WHERE id=?", (sid,)).fetchone()[0] == 0
    db.close()


# ---- counts, briefing, health -------------------------------------------------------------------------

def test_counts_briefing_and_health_leave_acked_issues_out(owner):
    sid, _, key = disk_server(owner, "nl-1", used=97)
    brief = owner.get("/api/v1/reports/briefing").json()
    assert brief["issues"]["critical"] == 1 and brief["check_first"][0]["code"] == "disk"
    health = next(s for s in owner.get("/api/v1/reports/health").json()["servers"] if s["server_id"] == sid)
    assert "disk" in [p["key"] for p in health["penalties"]] and health["open_issues"] == 1
    owner.post("/api/v1/issues/ack", json={"key": key, "mode": "7d", "note": "دیسک جدید سفارش داده شد"})
    assert owner.get("/api/v1/overview").json()["issues_critical"] == 0
    brief = owner.get("/api/v1/reports/briefing").json()
    assert brief["issues"]["critical"] == 0 and not [i for i in brief["issues"]["items"] if i["code"] == "disk"]
    assert not [s for s in brief["check_first"] if s["code"] == "disk"]
    (a,) = brief["acknowledged"]
    assert a["code"] == "disk" and a["mode"] == "7d" and a["by"] == "Emad" and a["note"] == "دیسک جدید سفارش داده شد"
    md = owner.get("/api/v1/reports/briefing?format=md").text
    assert "## Acknowledged by the team" in md and "دیسک جدید سفارش داده شد" in md
    health = next(s for s in owner.get("/api/v1/reports/health").json()["servers"] if s["server_id"] == sid)
    assert "disk" not in [p["key"] for p in health["penalties"]]
    assert health["open_issues"] == 0 and health["acked_issues"] == 1 and health["score"] == 100


def test_health_keeps_a_penalty_another_loud_issue_stands_behind():
    quiet = acks.health_quiet([{"code": "cpu", "acked": True}, {"code": "steal", "acked": False}, {"code": "disk", "acked": True}])
    assert quiet == {"disk"}
    score, gates, pens = acks.screen_health("offline", 0, [{"key": "agent_offline"}], [], {"agent_offline"})
    assert (score, gates) == (None, [])


# ---- workspaces and roles -----------------------------------------------------------------------------

@pytest.fixture
def world(owner, tg, monkeypatch):
    monkeypatch.setattr(ssl_svc, "is_public_host", lambda h: True)
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: {"not_after": int(time.time()) + 40 * 86400, "issuer": "LE", "error": None})
    return build(owner, tg)


def test_an_ack_never_reaches_or_hides_another_workspace_s_issue(world):
    x, y, b = world["x"], world["y"], world["b"]
    bx = b["servers"]["bee-exit"]
    report(y, b["agent_keys"]["bee-exit"], hostname="bee-exit", public_ip="203.0.113.2", ram_avail_mb=40)
    key = "server:%d:ram" % bx
    assert by_id(y, key)["acked"] is False
    r = x.post("/api/v1/issues/ack", json={"key": key, "mode": "always"})
    assert r.status_code == 404 and r.json()["code"] == "issue.not_found"
    db = connect()
    ack_row(db, key, "always", ws=world["A"])  # a row in A with B's key changes nothing in B
    db.close()
    assert by_id(y, key)["acked"] is False and y.get("/api/v1/overview").json()["issues_warning"] >= 1
    assert x.delete("/api/v1/issues/ack?key=server:%d:disk" % bx).json()["code"] == "ack.not_found"
    db = connect()
    assert ack_keys(db, world["B"]) == ["server:%d:disk" % bx]  # B's own ack is untouched
    db.close()


def test_operators_acknowledge_viewers_and_read_keys_do_not(team):  # noqa: F811
    _, _, key = disk_server(team["owner"], "op-disk")
    assert team["viewer"].post("/api/v1/issues/ack", json={"key": key, "mode": "24h"}).json()["code"] == "auth.forbidden"
    assert team["operator"].post("/api/v1/issues/ack", json={"key": key, "mode": "24h"}).status_code == 200
    assert team["viewer"].delete("/api/v1/issues/ack?key=" + key).json()["code"] == "auth.forbidden"
    assert team["operator"].delete("/api/v1/issues/ack?key=" + key).status_code == 204
    owner = team["owner"]
    read = owner.post("/api/v1/keys", json={"name": "r", "scope": "read"}).json()["token"]
    full = owner.post("/api/v1/keys", json={"name": "f", "scope": "full"}).json()["token"]
    plain = team["viewer"].__class__(owner.app)  # no cookie: only the key speaks
    r = plain.post("/api/v1/issues/ack", json={"key": key, "mode": "24h"}, headers={"Authorization": "Bearer " + read})
    assert r.status_code == 403 and r.json()["code"] == "auth.forbidden"
    r = plain.post("/api/v1/issues/ack", json={"key": key, "mode": "24h"}, headers={"Authorization": "Bearer " + full})
    assert r.status_code == 200
    assert plain.delete("/api/v1/issues/ack?key=" + key, headers={"Authorization": "Bearer " + read}).status_code == 403
