"""Two workspaces with data in every table, for the isolation, role and monitor tests.

A (workspace 1) belongs to the conftest owner X (Telegram 111). B is the personal workspace of Y (222), created at Y's first
sign-in. X is a viewer in B, Y a viewer in A, Carol (333) an admin in B only. B also holds a server with the same public IP
as A's exit, so a join on the IP alone would mix the two fleets."""
import time

from fastapi.testclient import TestClient

from app import bot
from app.db import connect
from checks_data import checks as checks_data
from checks_data import panel as panel_data
from conftest import report

X_TG, Y_TG, CAROL_TG = 111, 222, 333
A_IPS = {"alfa-relay": "198.51.100.1", "alfa-exit": "198.51.100.2"}
B_IPS = {"bee-relay": "203.0.113.1", "bee-exit": "203.0.113.2", "bee-twin": "198.51.100.2"}
A_MARKS = ("alfa-relay", "alfa-exit", "A-cat", "a-domain.example.com", "A-key", "-1001111111111", "A-incident", "A-chan",
           "alfa-node", "alfa-reseller", "alfa-inbound")
B_MARKS = ("bee-relay", "bee-exit", "bee-twin", "203.0.113.", "B-cat", "b-domain.example.com", "B-key", "-1002222222222",
           "B-incident", "B-chan", "bee-node", "bee-reseller", "bee-inbound", "bee-box", "bee_invitee")
# tables of the host checks and panel truth: every row carries workspace_id
CHECK_TABLES = ("listener_baseline", "check_state", "check_ignores", "node_usage")


def login(app, tg, tg_id) -> TestClient:
    """A separate browser signed in through the real Telegram challenge flow."""
    c = TestClient(app)
    start = c.post("/api/v1/auth/telegram/start").json()
    token = start["deep_link"].split("wl_")[1]
    bot.handle(tg, {"update_id": 1, "message": {"from": {"id": tg_id}, "chat": {"id": tg_id}, "text": "/start wl_" + token}})
    bot.handle(tg, {"update_id": 2, "callback_query": {"id": "x", "from": {"id": tg_id}, "data": "wl:ok:%d" % start["challenge_id"]}})
    r = c.post("/api/v1/auth/telegram/poll", json={"challenge_id": start["challenge_id"], "poll_secret": start["poll_secret"]})
    assert r.json()["status"] == "approved", r.text
    return c


def invite(client, tg_id, role, name=""):
    r = client.post("/api/v1/members", json={"tg_id": tg_id, "role": role, "name": name})
    assert r.status_code == 201, r.text
    return r.json()["user_id"]


def switch(client, ws):
    """What the switcher does: check the workspace with the master, then name it on every request of this tab."""
    r = client.post("/api/v1/auth/workspace", json={"workspace_id": ws})
    assert r.status_code == 200, r.text
    client.headers["X-Workspace-Id"] = str(ws)
    return r.json()


def join(ws, tg_id, role, added_by=None):
    """A membership written straight to the database: only the panel owner adds people through the API, so this is how
    a second workspace gets members in these tests."""
    db = connect()
    try:
        row = db.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,)).fetchone()
        uid = row["id"] if row else db.execute(
            "INSERT INTO users (tg_id, name, role, created_at) VALUES (?, '', 'none', ?)", (tg_id, int(time.time()))).lastrowid
        db.execute("INSERT INTO workspace_members (workspace_id, user_id, role, added_by, created_at) VALUES (?,?,?,?,?)",
                   (ws, uid, role, added_by, int(time.time())))
        return uid
    finally:
        db.close()


def add_server(client, name, role, ip):
    r = client.post("/api/v1/servers", json={"name": name, "role": role})
    assert r.status_code == 201, r.text
    token = r.json()["install_command"].split("--token ")[1]
    key = client.post("/api/agent/v1/enroll", json={"token": token, "hostname": name}).json()["agent_key"]
    sid = r.json()["server"]["id"]
    for _ in range(2):
        report(client, key, hostname=name, public_ip=ip)
    return sid, key


def _fill(client, ws, prefix, ips, chat):
    """One workspace's data: servers with metrics and pings, a category, domain, settings, key, channel, route, job,
    incident, link bytes and change-log lines."""
    now = int(time.time())
    ids, keys = {}, {}
    for name, ip in ips.items():
        ids[name], keys[name] = add_server(client, name, "relay" if name.endswith("relay") else "exit", ip)
    cat = client.post("/api/v1/categories", json={"name": prefix + "-cat"}).json()["id"]
    relay = next(n for n in ips if n.endswith("relay"))
    exit_ = next(n for n in ips if n.endswith("exit"))
    assert client.patch("/api/v1/servers/%d" % ids[exit_], json={"category_id": cat, "acct_on": True}).status_code == 200
    assert client.put("/api/v1/settings", json={"cpu_warn": 77 if prefix == "A" else 55}).status_code == 200
    key = client.post("/api/v1/keys", json={"name": prefix + "-key", "scope": "read"}).json()
    chan = client.post("/api/v1/telegram/channels", json={"name": prefix + "-chan", "chat_id": chat}).json()["id"]
    assert client.put("/api/v1/telegram/routes", json={"cpu": "channel:%d" % chan}).status_code == 200
    job = client.post("/api/v1/servers/%d/jobs" % ids[exit_], json={"kind": "ping"}).json()["id"]
    inv = client.post("/api/v1/members/invites", json={"tg_username": "@%s_invitee" % ("alfa" if prefix == "A" else "bee"), "role": "viewer"}).json()["id"]
    # the relay is also the panel host: host checks, a learned baseline, panel truth and an ignore of each kind
    tag = "alfa" if prefix == "A" else "bee"
    pan = panel_data(nodes=[{"id": 1, "name": tag + "-node", "address": "192.0.2.1", "port": 1, "status": "error", "message": ""}],
                     admins=[{"name": tag + "-reseller", "used": 99, "limit": 100}], inbounds_without_group=[tag + "-inbound"])
    pan["usage"] = {"hour_start": now // 3600 * 3600 - 3600, "last": [{"node_id": 1, "users": 5, "bytes": 9}], "prev": []}
    for _ in range(2):
        report(client, keys[relay], hostname=relay, public_ip=ips[relay], agent_version="0.3.1", uptime_s=1000,
               checks=checks_data(containers=[dict(checks_data()["containers"][0], name=tag + "-box")]), panel=pan)
    assert client.patch("/api/v1/servers/%d/ignores" % ids[relay], json={"kind": "container", "name": tag + "-box"}).status_code == 200
    db = connect()
    dom = db.execute(
        "INSERT INTO domains (workspace_id, host, port, note, created_at, last_checked, not_after) VALUES (?,?,443,'',?,?,?)",
        (ws, prefix.lower() + "-domain.example.com", now, now, now + 30 * 86400),
    ).lastrowid
    db.execute(
        "INSERT INTO incidents (workspace_id, key, code, server_id, server_name, severity, title, evidence, opened_at, last_seen, closed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (ws, "server:%d:disk" % ids[exit_], "disk", ids[exit_], exit_, "warning", prefix + "-incident", "{}", now - 7200, now - 3600, now - 3600),
    )
    for target in ips.values():
        for k in range(7):
            db.execute("INSERT INTO pings (server_id, ts, target, loss, rtt) VALUES (?,?,?,?,?)", (ids[relay], now - 20 - k * 30, target, 0.0, 40.0))
    db.execute("INSERT INTO link_traffic (server_id, peer_ip, hour, in_bytes, out_bytes) VALUES (?,?,?,?,?)",
               (ids[relay], ips[exit_], now - now % 3600 - 3600, 111, 222))
    rx = 1000 if prefix == "A" else 7_000_000  # distinct volumes, so a sum over both workspaces shows
    for sid in ids.values():
        for k in range(3):
            db.execute("INSERT INTO metrics (server_id, ts, cpu, rx_delta, tx_delta) VALUES (?,?,?,?,?)", (sid, now - 600 - k * 60, 10.0, rx, 2 * rx))
    if "bee-twin" in ips:  # B's relay also talks to its twin, whose IP is A's exit's too
        db.execute("INSERT INTO link_traffic (server_id, peer_ip, hour, in_bytes, out_bytes) VALUES (?,?,?,?,?)",
                   (ids[relay], ips["bee-twin"], now - now % 3600 - 3600, 5, 6))
    db.execute("INSERT INTO alert_state (workspace_id, key, level) VALUES (?,?,?)", (ws, "ssl:d%d" % dom, "ok"))
    db.execute("INSERT INTO flapping (workspace_id, key, since) VALUES (?,?,?)", (ws, prefix + "-flap", now))
    db.execute("INSERT INTO issue_acks (workspace_id, key, mode, severity, note, created_at) VALUES (?,?,'always','warning',?,?)",
               (ws, "server:%d:disk" % ids[exit_], prefix + "-incident", now))
    db.close()
    return {"servers": ids, "agent_keys": keys, "category": cat, "key": key["id"], "key_token": key["token"], "channel": chan,
            "job": job, "domain": dom, "invite": inv}


def build(owner, tg):
    """X is `owner` (signed in, workspace 1). Returns the clients and the ids of both workspaces."""
    app = owner.app
    y_id = invite(owner, Y_TG, "viewer", "Yasmin")
    y = login(app, tg, Y_TG)
    mine = [w for w in y.get("/api/v1/auth/workspaces").json() if w["is_personal"]]
    assert len(mine) == 1 and mine[0]["role"] == "owner"
    b = mine[0]["id"]
    # a first sign-in lands in the person's own workspace, never in one someone else joined them to
    assert y.get("/api/v1/auth/me").json()["workspace"]["id"] == b
    switch(y, b)
    owner.headers["X-Workspace-Id"] = "1"
    x_id = join(b, X_TG, "viewer", added_by=y_id)
    carol_id = join(b, CAROL_TG, "admin", added_by=y_id)
    world = {
        "app": app, "x": owner, "y": y, "A": 1, "B": b, "x_id": x_id, "y_id": y_id, "carol_id": carol_id,
        "a": _fill(owner, 1, "A", A_IPS, "-1001111111111"),
        "b": _fill(y, b, "B", B_IPS, "-1002222222222"),
    }
    return world


def dump(ws):
    """Every row a workspace owns, directly or through its servers, for before/after comparisons."""
    db = connect()
    try:
        out = {}
        for table in ("servers", "categories", "domains", "settings", "api_keys", "telegram_channels", "rule_routes",
                      "incidents", "events", "alert_state", "flapping", "issue_acks", "workspace_invites", "probe_ports"):
            out[table] = sorted(tuple(r) for r in db.execute("SELECT * FROM %s WHERE workspace_id=?" % table, (ws,)))
        for table in CHECK_TABLES:
            out[table] = sorted(tuple(r) for r in db.execute("SELECT * FROM %s WHERE workspace_id=?" % table, (ws,)))
        for table in ("jobs", "metrics", "pings", "probes", "link_traffic", "link_prev"):
            out[table] = sorted(tuple(r) for r in db.execute(
                "SELECT t.* FROM %s t JOIN servers s ON s.id=t.server_id WHERE s.workspace_id=?" % table, (ws,)))
        out["members"] = sorted(tuple(r) for r in db.execute("SELECT * FROM workspace_members WHERE workspace_id=?", (ws,)))
        return out
    finally:
        db.close()
