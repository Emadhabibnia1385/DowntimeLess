"""Phase 3 rules and the read-only view from `panel` (PasarGuard panel truth), on the real panel's shape."""
import copy

from app.db import connect
from checks_data import GIB, checks, panel
from conftest import make_server, report
from test_checks_host import clock, found  # noqa: F401 - the clock fixture

HOUR = 3600


def send(owner, key, clock, step=30, **over):
    clock[0] += step
    body = {"agent_version": "0.3.1", "uptime_s": 500000 + int(clock[0]) % 100000, "checks": checks(containers=[], container_logs=None)}
    body.update(over)
    assert report(owner, key, **body).status_code == 200


def last_hour(clock):
    return int(clock[0]) // HOUR * HOUR - HOUR


def with_usage(clock, users=None, **over):
    """The panel with this hour's usage: 300 users per node unless `users` maps node id -> users."""
    p = panel(**over)
    p["usage"]["hour_start"] = last_hour(clock)
    if users:
        for row in p["usage"]["last"]:
            if row["node_id"] in users:
                row["users"] = users[row["node_id"]]
                row["bytes"] = users[row["node_id"]] * 130 * 1024 ** 2
    return p


def history(sid, clock, users=300):
    db = connect()
    h = last_hour(clock)
    for k in range(1, 7):
        for nid in range(1, 23):
            db.execute("INSERT OR REPLACE INTO node_usage (workspace_id, server_id, node_id, hour, users, bytes) VALUES (1,?,?,?,?,?)",
                       (sid, nid, h - k * HOUR, users, 40 * GIB))
    db.close()


def test_real_panel_shape_raises_reseller_and_inbound_issues_only(owner, clock):
    sid, key = make_server(owner, "panel", "panel")
    send(owner, key, clock, panel=with_usage(clock))
    got = found(owner)
    resellers = sorted(c for c in got if c.startswith("reseller_quota:"))
    assert resellers == ["reseller_quota:reseller03", "reseller_quota:reseller17", "reseller_quota:reseller25"]
    r = got["reseller_quota:reseller03"]
    assert r["severity"] == "critical" and r["evidence"]["reseller"] == "reseller03" and r["evidence"]["used_pct"] == 97.0
    assert "reseller03" in r["title"]
    assert got["inbound_without_group"]["evidence"]["inbounds"] == ["wg0"]
    assert not [c for c in got if c.startswith(("node_down", "node_silent", "node_usage_drop", "panel_errors", "panel_version"))]
    # wg0 is group-less on purpose
    assert owner.patch("/api/v1/servers/%d/ignores" % sid, json={"kind": "inbound", "name": "wg0"}).status_code == 200
    assert "inbound_without_group" not in found(owner)


def test_reseller_thresholds_come_from_settings(owner, clock):
    sid, key = make_server(owner, "panel", "panel")
    owner.put("/api/v1/settings", json={"reseller_warn": 70, "reseller_crit": 99})
    send(owner, key, clock, panel=with_usage(clock))
    got = found(owner, "reseller_quota:")
    assert got["reseller_quota:reseller03"]["severity"] == "warning"
    assert got["reseller_quota:reseller06"]["severity"] == "warning"  # 80%: above the new warning line


def test_reseller_projected_to_run_out_within_a_day_is_critical(owner, clock):
    sid, key = make_server(owner, "panel", "panel")
    p = with_usage(clock)
    p["admins"] = [{"name": "fast", "used": 60 * GIB, "limit": 100 * GIB}]
    send(owner, key, clock, panel=p)
    assert "reseller_quota:fast" not in found(owner)
    p = copy.deepcopy(p)
    p["admins"][0]["used"] = 62 * GIB  # 2 GiB an hour, 38 GiB left: 19 hours
    send(owner, key, clock, step=HOUR, panel=p)
    issue = found(owner)["reseller_quota:fast"]
    assert issue["severity"] == "critical" and 18 <= issue["evidence"]["hours_left"] <= 20
    view = owner.get("/api/v1/panel").json()["panels"][0]["resellers"][0]
    assert view["name"] == "fast" and view["level"] == "critical" and view["per_hour"] > 0


def test_node_down_after_five_minutes_and_disabled_nodes_are_ignored(owner, clock):
    sid, key = make_server(owner, "panel", "panel")
    p = with_usage(clock)
    p["nodes"][4]["status"] = "error"
    p["nodes"][4]["message"] = "Request timed out"
    send(owner, key, clock, panel=p)
    send(owner, key, clock, step=200, panel=p)
    assert "node_down:5" not in found(owner)
    send(owner, key, clock, step=120, panel=p)
    issue = found(owner)["node_down:5"]
    assert issue["severity"] == "critical" and issue["evidence"]["node"] == "node-05" and issue["evidence"]["message"] == "Request timed out"
    assert "node_down:23" not in found(owner)  # disabled
    owner.patch("/api/v1/servers/%d/ignores" % sid, json={"kind": "node", "name": "5"})  # retired node
    assert "node_down:5" not in found(owner)


def test_connected_node_with_unavailable_logs_is_silent(owner, clock):
    sid, key = make_server(owner, "panel", "panel")
    exit_, ekey = make_server(owner, "de-1", "exit")
    logs = [{"container": "pasarguard-node-1", "unavailable": 9, "keepalive": 0, "queuepool": 0, "certfail": 0}]
    send(owner, ekey, clock, public_ip="198.51.100.102", checks=checks(container_logs=logs))
    send(owner, key, clock, panel=with_usage(clock))
    issue = found(owner)["node_silent:2"]
    assert issue["severity"] == "critical" and "Xray" in issue["title"] and issue["evidence"]["reason"] == ["logs"]
    assert issue["evidence"]["unavailable_10m"] == 9


def test_usage_collapse_is_silent_and_a_partial_drop_is_a_usage_drop(owner, clock):
    sid, key = make_server(owner, "panel", "panel")
    history(sid, clock)
    send(owner, key, clock, panel=with_usage(clock, {5: 20, 6: 70}))
    got = found(owner)
    assert got["node_silent:5"]["evidence"]["reason"] == ["usage"] and got["node_silent:5"]["evidence"]["users_median"] == 300
    drop = got["node_usage_drop:6"]
    assert drop["severity"] == "warning" and drop["evidence"]["users_pct"] == 23.3 and drop["evidence"]["others_pct"] >= 70
    nodes = {n["id"]: n for n in owner.get("/api/v1/panel").json()["panels"][0]["nodes"]}
    assert nodes[6]["dropped"] and nodes[6]["users_median"] == 300 and not nodes[7]["dropped"] and nodes[23]["enabled"] is False


def test_a_quiet_night_on_every_node_is_not_an_alarm(owner, clock):
    sid, key = make_server(owner, "panel", "panel")
    history(sid, clock)
    send(owner, key, clock, panel=with_usage(clock, {i: 60 for i in range(1, 23)}))
    assert not [c for c in found(owner) if c.startswith(("node_usage_drop", "node_silent"))]


def test_a_short_history_has_no_median(owner, clock):
    sid, key = make_server(owner, "panel", "panel")
    send(owner, key, clock, panel=with_usage(clock, {5: 0}))
    assert not [c for c in found(owner) if c.startswith(("node_usage_drop", "node_silent"))]
    db = connect()
    rows = db.execute("SELECT COUNT(*) FROM node_usage WHERE server_id=?", (sid,)).fetchone()[0]
    db.close()
    assert rows == 46  # 23 nodes x (last hour, the hour before)


def test_version_change_and_read_errors_are_info(owner, clock):
    sid, key = make_server(owner, "panel", "panel")
    send(owner, key, clock, panel=with_usage(clock))
    send(owner, key, clock, panel=with_usage(clock, version="5.7.0", errors=["admins:OperationalError"]))
    got = found(owner)
    assert got["panel_version_changed"]["evidence"] == {"old_version": "5.6.0", "new_version": "5.7.0"}
    assert got["panel_errors"]["severity"] == "info" and got["panel_errors"]["evidence"]["errors"] == ["admins:OperationalError"]
    send(owner, key, clock, panel=None, panel_error="Timeout")
    got = found(owner)
    assert got["panel_errors"]["evidence"]["errors"] == ["Timeout"]
    assert not [c for c in got if c.startswith(("reseller_quota", "inbound_without_group", "node_"))]  # no panel, no verdict


def test_panel_view_and_briefing(owner, clock):
    sid, key = make_server(owner, "panel", "panel")
    assert owner.get("/api/v1/panel").json()["panels"] == []
    send(owner, key, clock, panel=with_usage(clock))
    out = owner.get("/api/v1/panel").json()
    assert out["reseller_warn"] == 85 and len(out["panels"]) == 1
    p = out["panels"][0]
    assert p["version"] == "5.6.0" and len(p["nodes"]) == 23 and len(p["resellers"]) == 40  # the sudo admin has no limit
    assert p["user_status"]["active"] == 8410 and p["inbounds_without_group"] == [{"tag": "wg0", "ignored": False}]
    assert p["resellers"][0]["used_pct"] == 97.0
    assert "password" not in str(out).lower() and "token" not in str(out).lower()
    b = owner.get("/api/v1/reports/briefing?detail=full").json()["panel"][0]
    assert (b["nodes_total"], b["connected"], b["disabled"]) == (23, 22, 1)
    assert b["users_last_hour"] == 6600 and len(b["resellers_near_quota"]) == 3 and b["inbounds_without_group"] == ["wg0"]
    md = owner.get("/api/v1/reports/briefing?format=md").text
    assert "## PasarGuard panel on panel" in md and "reseller03" in md
    health = [s for s in owner.get("/api/v1/reports/health").json()["servers"] if s["server_id"] == sid][0]
    assert health["band"] == "healthy"


def test_roles_viewers_read_and_only_admins_ignore(owner, tg, clock):
    from ws_world import invite, login, switch
    sid, key = make_server(owner, "panel", "panel")
    send(owner, key, clock, panel=with_usage(clock))
    invite(owner, 404, "operator")
    op = login(owner.app, tg, 404)
    switch(op, 1)
    assert op.get("/api/v1/panel").status_code == 200 and op.get("/api/v1/servers/%d/host-health" % sid).status_code == 200
    r = op.patch("/api/v1/servers/%d/ignores" % sid, json={"kind": "inbound", "name": "wg0"})
    assert r.status_code == 403 and r.json()["code"] == "auth.forbidden"
    assert op.patch("/api/v1/servers/%d/listeners" % sid, json={"proto": "tcp", "port": 22}).status_code == 403
