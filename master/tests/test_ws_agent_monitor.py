"""Agents and the monitor stay inside their workspace: targets, peers, writes, alerts and channels."""
import time

import pytest

from app import monitor
from app.db import connect
from app.features.ssl import service as ssl_svc
from conftest import report
from ws_world import A_IPS, B_IPS, CAROL_TG, X_TG, Y_TG, build, dump


@pytest.fixture
def world(owner, tg, monkeypatch):
    monkeypatch.setattr(ssl_svc, "is_public_host", lambda h: True)
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: {"not_after": int(time.time()) + 40 * 86400, "issuer": "LE", "error": None})
    w = build(owner, tg)
    tg.sent.clear()
    return w


def test_relays_get_ping_targets_of_their_own_workspace_only(world):
    x = world["x"]
    a = report(x, world["a"]["agent_keys"]["alfa-relay"]).json()
    b = report(x, world["b"]["agent_keys"]["bee-relay"]).json()
    assert sorted(t["target"] for t in a["ping_targets"]) == [A_IPS["alfa-exit"]]
    assert sorted(t["target"] for t in b["ping_targets"]) == sorted([B_IPS["bee-exit"], B_IPS["bee-twin"]])


def test_byte_counting_peers_are_the_own_workspace_s_servers(world):
    x = world["x"]
    sid = world["a"]["servers"]["alfa-relay"]
    x.patch("/api/v1/servers/%d" % sid, json={"acct_on": True})
    peers = report(x, world["a"]["agent_keys"]["alfa-relay"]).json()["acct_peers"]
    assert peers == [A_IPS["alfa-exit"]]
    y = world["y"]
    y.patch("/api/v1/servers/%d" % world["b"]["servers"]["bee-relay"], json={"acct_on": True})
    peers = report(x, world["b"]["agent_keys"]["bee-relay"]).json()["acct_peers"]
    assert sorted(peers) == sorted([B_IPS["bee-exit"], B_IPS["bee-twin"]])


def test_an_agent_cannot_write_into_another_workspace(world):
    x, before_b = world["x"], dump(world["B"])
    b_job = world["b"]["job"]
    key = world["a"]["agent_keys"]["alfa-exit"]
    r = report(x, key, jobs_done=[{"id": b_job, "status": "ok", "result": {"stolen": 1}}],
               ssl={"domains": ["b-domain.example.com"]}, acct={B_IPS["bee-exit"]: {"in": 5, "out": 5}})
    assert r.status_code == 200
    assert r.json()["jobs"] and all(j["id"] != b_job for j in r.json()["jobs"])  # A's own queued ping, never B's
    assert dump(world["B"]) == before_b
    db = connect()
    # the discovered name joins A's own list; B's row of the same name is untouched
    rows = db.execute("SELECT workspace_id, source FROM domains WHERE host='b-domain.example.com' ORDER BY workspace_id").fetchall()
    db.close()
    assert [tuple(r) for r in rows] == [(1, "auto"), (world["B"], "manual")]


def _quiet(sid):
    db = connect()
    db.execute("UPDATE servers SET last_seen=? WHERE id=?", (int(time.time()) - 1000, sid))
    db.close()


def _to(tg, chat):
    return [m[1] for m in tg.sent if m[0] == chat]


def test_the_sweep_tells_each_workspace_s_admins_about_its_own_fleet_only(world, tg):
    _quiet(world["a"]["servers"]["alfa-exit"])
    _quiet(world["b"]["servers"]["bee-exit"])
    monitor.sweep(tg)
    x_msgs, y_msgs, carol_msgs = _to(tg, X_TG), _to(tg, Y_TG), _to(tg, CAROL_TG)
    # X: owner of A (gets A), viewer of B (gets nothing of B); Y: viewer of A, owner of B; Carol: admin of B
    assert x_msgs and all("alfa-exit" in m for m in x_msgs if "گزارش نمی‌دهد" in m)
    assert not any("bee-" in m for m in x_msgs)
    assert any("bee-exit" in m for m in y_msgs) and not any("alfa-" in m for m in y_msgs)
    assert any("bee-exit" in m for m in carol_msgs) and not any("alfa-" in m for m in carol_msgs)


def test_channel_routes_belong_to_their_workspace(world, tg):
    x, y = world["x"], world["y"]
    x.put("/api/v1/telegram/routes", json={"offline": "channel:%d" % world["a"]["channel"]})
    y.put("/api/v1/telegram/routes", json={"offline": "channel:%d" % world["b"]["channel"]})
    _quiet(world["a"]["servers"]["alfa-exit"])
    _quiet(world["b"]["servers"]["bee-exit"])
    monitor.sweep(tg)
    a_chan, b_chan = _to(tg, -1001111111111), _to(tg, -1002222222222)
    assert a_chan and all("alfa-exit" in m for m in a_chan)
    assert b_chan and all("bee-exit" in m for m in b_chan)
    assert not any("گزارش نمی‌دهد" in m for m in _to(tg, X_TG) + _to(tg, Y_TG))


def test_incidents_and_their_alerts_are_recorded_per_workspace(world, tg):
    x = world["x"]
    report(x, world["b"]["agent_keys"]["bee-exit"], public_ip=B_IPS["bee-exit"], disk_used_gb=96)
    monitor.sweep(tg)
    db = connect()
    rows = db.execute("SELECT workspace_id, server_name FROM incidents WHERE code='disk' AND closed_at IS NULL").fetchall()
    events = db.execute("SELECT workspace_id FROM events WHERE kind='issue_opened' AND title LIKE 'bee-exit%'").fetchall()
    db.close()
    assert [tuple(r) for r in rows] == [(world["B"], "bee-exit")]
    assert {r["workspace_id"] for r in events} == {world["B"]}
    disk = [m for m in tg.sent if "دیسک" in m[1]]
    assert disk and {m[0] for m in disk} == {Y_TG, CAROL_TG}  # B's owner and admin, nobody of A
    assert "bee-exit" not in x.get("/api/v1/issues").text
    assert "bee-exit" in world["y"].get("/api/v1/issues").text


def test_thresholds_are_per_workspace(world, tg):
    x, y = world["x"], world["y"]
    x.put("/api/v1/settings", json={"on_disk": 0})
    report(x, world["a"]["agent_keys"]["alfa-exit"], public_ip=A_IPS["alfa-exit"], disk_used_gb=96)
    report(x, world["b"]["agent_keys"]["bee-exit"], public_ip=B_IPS["bee-exit"], disk_used_gb=96)
    assert not any(i["code"] == "disk" for i in x.get("/api/v1/issues").json())
    assert any(i["code"] == "disk" for i in y.get("/api/v1/issues").json())
    assert y.get("/api/v1/settings").json()["on_disk"] == 1
