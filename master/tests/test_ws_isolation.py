"""Acting in workspace A never reads, changes or deletes workspace B's rows, on every endpoint the API has."""
import time

import pytest
from fastapi.routing import APIRoute

from app.features.ssl import service as ssl_svc
from test_workspace_guard import NOT_SCOPED, NOT_SCOPED_EXACT
from ws_world import A_MARKS, B_MARKS, build, dump, switch

NOT_FOUND = {"server.not_found", "category.not_found", "domain.not_found", "key.not_found", "channel.not_found",
             "member.not_found"}


@pytest.fixture
def world(owner, tg, monkeypatch):
    monkeypatch.setattr(ssl_svc, "is_public_host", lambda h: True)
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: {"not_after": int(time.time()) + 40 * 86400, "issuer": "LE", "error": None})
    return build(owner, tg)


def requests_into_b(w):
    """Every route of the API, called from A with B's ids wherever an id goes (path, query or body).

    The value says what must come back: 'nf' = one of the not-found codes, or an expected (status, code)."""
    b = w["b"]
    bs, bx = b["servers"]["bee-relay"], b["servers"]["bee-exit"]
    a_exit = w["a"]["servers"]["alfa-exit"]
    s = "/api/v1/servers/%d" % bx
    return {
        ("GET", "/api/v1/servers"): ("GET", "/api/v1/servers", None, "list"),
        ("POST", "/api/v1/servers"): ("POST", "/api/v1/servers", {"name": "a-new", "category_id": b["category"]}, (404, "category.not_found")),
        ("POST", "/api/v1/servers/{server_id}/enroll-token"): ("POST", s + "/enroll-token", None, "nf"),
        ("GET", "/api/v1/servers/{server_id}"): ("GET", s, None, "nf"),
        ("PATCH", "/api/v1/servers/{server_id}"): ("PATCH", s, {"name": "stolen"}, "nf"),
        ("DELETE", "/api/v1/servers/{server_id}"): ("DELETE", s, None, "nf"),
        ("GET", "/api/v1/servers/{server_id}/metrics"): ("GET", s + "/metrics", None, "nf"),
        ("GET", "/api/v1/servers/{server_id}/jobs"): ("GET", s + "/jobs", None, "nf"),
        ("POST", "/api/v1/servers/{server_id}/jobs"): ("POST", s + "/jobs", {"kind": "reboot"}, "nf"),
        ("GET", "/api/v1/categories"): ("GET", "/api/v1/categories", None, "list"),
        ("POST", "/api/v1/categories"): ("POST", "/api/v1/categories", {"name": "a-new-cat"}, (201, None)),
        ("PATCH", "/api/v1/categories/{category_id}"): ("PATCH", "/api/v1/categories/%d" % b["category"], {"name": "stolen"}, "nf"),
        ("DELETE", "/api/v1/categories/{category_id}"): ("DELETE", "/api/v1/categories/%d" % b["category"], None, "nf"),
        ("GET", "/api/v1/overview"): ("GET", "/api/v1/overview", None, "list"),
        ("GET", "/api/v1/overview/history"): ("GET", "/api/v1/overview/history", None, "list"),
        ("GET", "/api/v1/issues"): ("GET", "/api/v1/issues", None, "list"),
        ("GET", "/api/v1/ping-matrix"): ("GET", "/api/v1/ping-matrix", None, "list"),
        ("GET", "/api/v1/snapshot"): ("GET", "/api/v1/snapshot", None, "list"),
        ("GET", "/api/v1/issues/history"): ("GET", "/api/v1/issues/history?range=30d", None, "list"),
        ("GET", "/api/v1/settings"): ("GET", "/api/v1/settings", None, "list"),
        ("PUT", "/api/v1/settings"): ("PUT", "/api/v1/settings", {"cpu_warn": 12}, (200, None)),
        ("GET", "/api/v1/keys"): ("GET", "/api/v1/keys", None, "list"),
        ("POST", "/api/v1/keys"): ("POST", "/api/v1/keys", {"name": "a2", "scope": "read"}, (201, None)),
        ("DELETE", "/api/v1/keys/{key_id}"): ("DELETE", "/api/v1/keys/%d" % b["key"], None, "nf"),
        ("GET", "/api/v1/ssl"): ("GET", "/api/v1/ssl", None, "list"),
        ("POST", "/api/v1/domains"): ("POST", "/api/v1/domains", {"host": "a-new.example.com"}, (201, None)),
        ("POST", "/api/v1/domains/{domain_id}/check"): ("POST", "/api/v1/domains/%d/check" % b["domain"], None, "nf"),
        ("DELETE", "/api/v1/domains/{domain_id}"): ("DELETE", "/api/v1/domains/%d" % b["domain"], None, "nf"),
        ("GET", "/api/v1/links/traffic"): ("GET", "/api/v1/links/traffic", None, "list"),
        ("GET", "/api/v1/links/traffic/series"): ("GET", "/api/v1/links/traffic/series?server_id=%d&peer_ip=203.0.113.2" % bs, None, "nf"),
        ("GET", "/api/v1/traffic/summary"): ("GET", "/api/v1/traffic/summary", None, "list"),
        ("GET", "/api/v1/traffic/series"): ("GET", "/api/v1/traffic/series?server_id=%d" % bx, None, "nf"),
        ("GET", "/api/v1/telegram/channels"): ("GET", "/api/v1/telegram/channels", None, "list"),
        ("POST", "/api/v1/telegram/channels"): ("POST", "/api/v1/telegram/channels", {"name": "x", "chat_id": "-1003333333333"}, (201, None)),
        ("DELETE", "/api/v1/telegram/channels/{channel_id}"): ("DELETE", "/api/v1/telegram/channels/%d" % b["channel"], None, "nf"),
        ("POST", "/api/v1/telegram/channels/{channel_id}/test"): ("POST", "/api/v1/telegram/channels/%d/test" % b["channel"], None, "nf"),
        ("GET", "/api/v1/telegram/routes"): ("GET", "/api/v1/telegram/routes", None, "list"),
        ("PUT", "/api/v1/telegram/routes"): ("PUT", "/api/v1/telegram/routes", {"ram": "channel:%d" % b["channel"]}, (422, "route.unknown_channel")),
        ("GET", "/api/v1/reports/briefing"): ("GET", "/api/v1/reports/briefing?detail=full", None, "list"),
        ("GET", "/api/v1/reports/playbooks"): ("GET", "/api/v1/reports/playbooks", None, "list"),
        ("GET", "/api/v1/reports/playbooks/{code}"): ("GET", "/api/v1/reports/playbooks/disk", None, "list"),
        ("GET", "/api/v1/reports/health"): ("GET", "/api/v1/reports/health", None, "list"),
        ("GET", "/api/v1/reports/changes"): ("GET", "/api/v1/reports/changes?server_id=%d" % bx, None, "empty_events"),
        ("GET", "/api/v1/reports/daily"): ("GET", "/api/v1/reports/daily", None, "list"),
        ("GET", "/api/v1/reports/incidents"): ("GET", "/api/v1/reports/incidents?since=%d" % (int(time.time()) - 86400 * 30), None, "list"),
        ("GET", "/api/v1/reports/traffic"): ("GET", "/api/v1/reports/traffic", None, "list"),
        ("GET", "/api/v1/reports/availability"): ("GET", "/api/v1/reports/availability", None, "list"),
        ("GET", "/api/v1/reports/capacity"): ("GET", "/api/v1/reports/capacity", None, "list"),
        ("GET", "/api/v1/reports/relays"): ("GET", "/api/v1/reports/relays", None, "list"),
        ("GET", "/api/v1/members"): ("GET", "/api/v1/members", None, "list"),
        ("POST", "/api/v1/members"): ("POST", "/api/v1/members", {"tg_id": 909, "role": "viewer"}, (201, None)),
        ("PATCH", "/api/v1/members/{user_id}"): ("PATCH", "/api/v1/members/%d" % w["carol_id"], {"role": "viewer"}, "nf"),
        ("DELETE", "/api/v1/members/{user_id}"): ("DELETE", "/api/v1/members/%d" % w["carol_id"], None, "nf"),
        # also with an id of A, to prove A's own rows still answer: the ping matrix must name A's exit, not B's twin
        ("A-check", "ping"): ("GET", "/api/v1/ping-matrix", None, ("names", a_exit)),
        # B's category as a filter: nothing comes back, never B's rows
        ("A-check", "cat-summary"): ("GET", "/api/v1/traffic/summary?category=%d" % b["category"], None, "list"),
        ("A-check", "cat-series"): ("GET", "/api/v1/traffic/series?category=%d" % b["category"], None, "list"),
        ("A-check", "cat-links"): ("GET", "/api/v1/links/traffic?category=%d" % b["category"], None, "list"),
        ("A-check", "cat-none"): ("GET", "/api/v1/links/traffic?category=none", None, "list"),
    }


def _scoped_routes(app):
    out = set()
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path not in NOT_SCOPED_EXACT and not r.path.startswith(NOT_SCOPED):
            out |= {(m, r.path) for m in r.methods}
    return out


def test_the_isolation_table_covers_every_route(world):
    table = requests_into_b(world)
    assert _scoped_routes(world["app"]) == {k for k in table if k[0] != "A-check"}


def test_acting_in_a_never_reads_changes_or_deletes_b(world):
    x, before_b = world["x"], dump(world["B"])
    for key, (method, url, body, expect) in requests_into_b(world).items():
        r = x.request(method, url, json=body)
        text = r.text
        assert not any(m in text for m in B_MARKS), (key, [m for m in B_MARKS if m in text])
        if expect == "nf":
            assert r.status_code == 404 and r.json()["code"] in NOT_FOUND, (key, r.status_code, text[:200])
        elif expect == "list":
            assert r.status_code == 200, (key, r.status_code, text[:200])
        elif expect == "empty_events":
            assert r.status_code == 200 and r.json()["events"] == [], key
        elif expect[0] == "names":
            cells = r.json()
            assert cells and {c["to_name"] for c in cells} == {"alfa-exit"} and {c["to_id"] for c in cells} == {expect[1]}, cells
        else:
            status, code = expect
            assert r.status_code == status, (key, r.status_code, text[:200])
            if code:
                assert r.json()["code"] == code, key
    assert dump(world["B"]) == before_b  # not one row of B moved


def test_lists_in_a_do_show_a(world):
    x = world["x"]
    assert {s["name"] for s in x.get("/api/v1/servers").json()} == {"alfa-relay", "alfa-exit"}
    text = "".join(x.get(u).text for u in ("/api/v1/servers", "/api/v1/categories", "/api/v1/ssl", "/api/v1/keys",
                                           "/api/v1/telegram/channels", "/api/v1/issues/history?range=24h"))
    assert all(m in text for m in A_MARKS), [m for m in A_MARKS if m not in text]
    assert x.get("/api/v1/settings").json()["cpu_warn"] == 77
    links = x.get("/api/v1/links/traffic").json()["links"]
    # not B's twin with the same IP, and its bytes counted once
    assert [(l["server_name"], l["peer_name"], l["in_bytes"], l["out_bytes"]) for l in links] == [("alfa-relay", "alfa-exit", 111, 222)]
    pairs = x.get("/api/v1/reports/traffic").json()["link_pairs"]
    assert [(p["server"], p["peer"], p["in_bytes"]) for p in pairs] == [("alfa-relay", "alfa-exit", 111)]
    assert x.get("/api/v1/overview").json()["servers_total"] == 2


def test_switching_to_b_shows_only_b_and_a_ids_vanish(world):
    x = world["x"]
    me = switch(x, world["B"])
    assert me["workspace"]["id"] == world["B"] and me["role"] == "viewer" and me["workspace"]["is_personal"] is False
    assert x.get("/api/v1/auth/me").json()["workspace"]["id"] == world["B"]
    text = "".join(x.get(u).text for u in ("/api/v1/servers", "/api/v1/categories", "/api/v1/ssl", "/api/v1/snapshot",
                                           "/api/v1/ping-matrix", "/api/v1/reports/briefing?detail=full", "/api/v1/links/traffic",
                                           "/api/v1/traffic/summary", "/api/v1/reports/changes", "/api/v1/issues/history?range=24h",
                                           "/api/v1/reports/traffic", "/api/v1/reports/relays", "/api/v1/reports/health",
                                           "/api/v1/reports/daily", "/api/v1/reports/capacity", "/api/v1/reports/availability"))
    assert not any(m in text for m in A_MARKS), [m for m in A_MARKS if m in text]
    links = {(l["server_name"], l["peer_name"], l["in_bytes"]) for l in x.get("/api/v1/links/traffic").json()["links"]}
    assert links == {("bee-relay", "bee-exit", 111), ("bee-relay", "bee-twin", 5)}
    assert "bee-relay" in text and "bee-twin" in text
    assert x.get("/api/v1/settings").json()["cpu_warn"] == 55
    a_exit = world["a"]["servers"]["alfa-exit"]
    assert x.get("/api/v1/servers/%d" % a_exit).json()["code"] == "server.not_found"
    # a viewer in B: reads, never changes
    assert x.patch("/api/v1/servers/%d" % world["b"]["servers"]["bee-exit"], json={"name": "z"}).json()["code"] == "auth.forbidden"
    assert x.get("/api/v1/keys").status_code == 403 and x.get("/api/v1/members").status_code == 403
    switch(x, world["A"])
    assert {s["name"] for s in x.get("/api/v1/servers").json()} == {"alfa-relay", "alfa-exit"}


def test_b_owner_sees_b_and_cannot_reach_a(world):
    y, before_a = world["y"], dump(world["A"])
    a = world["a"]
    for method, url, body in (
        ("GET", "/api/v1/servers/%d" % a["servers"]["alfa-exit"], None),
        ("DELETE", "/api/v1/servers/%d" % a["servers"]["alfa-exit"], None),
        ("POST", "/api/v1/servers/%d/jobs" % a["servers"]["alfa-exit"], {"kind": "reboot"}),
        ("DELETE", "/api/v1/categories/%d" % a["category"], None),
        ("DELETE", "/api/v1/keys/%d" % a["key"], None),
        ("DELETE", "/api/v1/telegram/channels/%d" % a["channel"], None),
        ("DELETE", "/api/v1/domains/%d" % a["domain"], None),
        ("DELETE", "/api/v1/members/%d" % world["x_id"], None),  # X is a member of B too: that one is B's to remove
    ):
        r = y.request(method, url, json=body)
        if url.endswith("/members/%d" % world["x_id"]):
            assert r.status_code == 204
            continue
        assert r.status_code == 404 and r.json()["code"] in NOT_FOUND, (url, r.text)
    assert dump(world["A"]) == before_a


def test_a_foreign_or_unknown_workspace_cannot_be_switched_to(world, owner, tg):
    from ws_world import CAROL_TG, login

    carol = login(world["app"], tg, CAROL_TG)
    switch(carol, world["B"])
    assert carol.post("/api/v1/auth/workspace", json={"workspace_id": world["A"]}).json()["code"] == "workspace.not_found"
    assert carol.post("/api/v1/auth/workspace", json={"workspace_id": 999}).json()["code"] == "workspace.not_found"
    assert {s["name"] for s in carol.get("/api/v1/servers").json()} == {"bee-relay", "bee-exit", "bee-twin"}


def test_names_and_chats_are_unique_per_workspace_only(world):
    x = world["x"]
    assert x.post("/api/v1/categories", json={"name": "B-cat"}).status_code == 201
    assert x.post("/api/v1/categories", json={"name": "B-cat"}).json()["code"] == "category.exists"
    # one chat belongs to one workspace; B's chat answers like a malformed id, so A learns nothing about it
    assert x.post("/api/v1/telegram/channels", json={"name": "c", "chat_id": "-1002222222222"}).json()["code"] == "channel.invalid"
    assert x.post("/api/v1/domains", json={"host": "b-domain.example.com"}).status_code == 201
    assert x.post("/api/v1/domains", json={"host": "b-domain.example.com"}).json()["code"] == "domain.exists"
    y = world["y"]
    assert [c["name"] for c in y.get("/api/v1/categories").json()] == ["B-cat"]
    assert len(y.get("/api/v1/telegram/channels").json()) == 1


def _expected_bytes(ws):
    from app.db import connect

    db = connect()
    r = db.execute("SELECT SUM(m.rx_delta) rx, SUM(m.tx_delta) tx FROM metrics m JOIN servers s ON s.id=m.server_id WHERE s.workspace_id=?",
                   (ws,)).fetchone()
    db.close()
    return r["rx"], r["tx"]


@pytest.mark.parametrize("side", ["A", "B"])
def test_fleet_totals_add_up_only_the_workspace_s_own_servers(world, side):
    c = world["x"] if side == "A" else world["y"]
    rx, tx = _expected_bytes(world[side])
    assert rx > 0
    ov = c.get("/api/v1/overview").json()
    assert (ov["rx_bytes_24h"], ov["tx_bytes_24h"]) == (rx, tx)
    assert c.get("/api/v1/traffic/summary").json()["fleet"]["period"]["rx"] == rx
    assert c.get("/api/v1/traffic/series?range=24h").json()["rx_total"] == rx
    assert c.get("/api/v1/overview/history?range=24h").json()["rx_total"] == rx
    rep = c.get("/api/v1/reports/traffic").json()
    assert rep["fleet"]["rx"] == rx and sum(s["rx"] for s in rep["servers"]) == rx
    assert c.get("/api/v1/reports/briefing").json()["traffic"]["last_7d"]["rx"] == rx
    assert c.get("/api/v1/reports/daily").json()["traffic"]["total"] == rx + tx
    servers = {s["server_id"] for s in c.get("/api/v1/reports/capacity").json()["servers"]}
    servers |= {s["server_id"] for s in c.get("/api/v1/reports/availability").json()["servers"]}
    servers |= {s["server_id"] for s in c.get("/api/v1/reports/health").json()["servers"]}
    assert servers == set(world[side.lower()]["servers"].values())


def test_a_category_filter_only_ever_looks_inside_the_active_workspace(world):
    x, y = world["x"], world["y"]
    b_cat, a_cat = world["b"]["category"], world["a"]["category"]
    for c, foreign in ((x, b_cat), (y, a_cat)):
        summary = c.get("/api/v1/traffic/summary?category=%d" % foreign).json()
        assert summary["servers"] == [] and summary["fleet"]["period"]["total"] == 0
        assert c.get("/api/v1/traffic/series?range=24h&category=%d" % foreign).json()["rx_total"] == 0
        assert c.get("/api/v1/links/traffic?category=%d" % foreign).json()["links"] == []
        assert c.get("/api/v1/traffic/summary?category=999999").json()["servers"] == []
        assert c.get("/api/v1/traffic/summary?category=abc").json()["code"] == "traffic.category_invalid"
    mine = x.get("/api/v1/traffic/summary?category=%d" % a_cat).json()
    assert [s["name"] for s in mine["servers"]] == ["alfa-exit"] and mine["fleet"]["period"]["rx"] == 3000
    links = x.get("/api/v1/links/traffic?category=%d" % a_cat).json()["links"]
    assert [(l["server_name"], l["peer_name"]) for l in links] == [("alfa-relay", "alfa-exit")]  # the peer is in it
    none = x.get("/api/v1/traffic/summary?category=none").json()
    assert [s["name"] for s in none["servers"]] == ["alfa-relay"]
    theirs = y.get("/api/v1/traffic/summary?category=%d" % b_cat).json()
    assert [s["name"] for s in theirs["servers"]] == ["bee-exit"]
