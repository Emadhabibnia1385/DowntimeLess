"""Who may do what inside one workspace: viewer < operator < admin < owner, enforced on the server for every endpoint."""
import time

import pytest

from app.db import connect
from app.features.ssl import service as ssl_svc
from conftest import make_server
from ws_world import invite, login, switch

RANK = {"viewer": 1, "operator": 2, "admin": 3, "owner": 4}


@pytest.fixture
def team(owner, tg, monkeypatch):
    monkeypatch.setattr(ssl_svc, "is_public_host", lambda h: True)
    monkeypatch.setattr(ssl_svc, "probe", lambda h, p: {"not_after": int(time.time()) + 40 * 86400, "issuer": "LE", "error": None})
    clients = {"owner": owner}
    for tg_id, role in ((401, "admin"), (402, "operator"), (403, "viewer")):
        invite(owner, tg_id, role)
        clients[role] = login(owner.app, tg, tg_id)
        switch(clients[role], 1)
        assert clients[role].get("/api/v1/auth/me").json()["role"] == role
    return clients


def _fresh(owner):
    """New rows for each call, so an allowed delete never takes away the next call's target."""
    sid, _ = make_server(owner, "s-%d" % time.monotonic_ns())
    cat = owner.post("/api/v1/categories", json={"name": "c-%d" % time.monotonic_ns()}).json()["id"]
    chan = owner.post("/api/v1/telegram/channels", json={"name": "c", "chat_id": "-100%d" % (time.monotonic_ns() % 10 ** 12)}).json()["id"]
    key = owner.post("/api/v1/keys", json={"name": "k", "scope": "read"}).json()["id"]
    db = connect()
    dom = db.execute("INSERT INTO domains (workspace_id, host, created_at) VALUES (1, ?, 1)", ("d%d.example.com" % time.monotonic_ns(),)).lastrowid
    db.close()
    return {"sid": sid, "cat": cat, "chan": chan, "key": key, "dom": dom}


# (method, path, body, the lowest role that may)
MATRIX = [
    ("GET", "/api/v1/servers", None, "viewer"),
    ("GET", "/api/v1/servers/{sid}", None, "viewer"),
    ("GET", "/api/v1/servers/{sid}/metrics", None, "viewer"),
    ("GET", "/api/v1/servers/{sid}/jobs", None, "viewer"),
    ("GET", "/api/v1/overview", None, "viewer"),
    ("GET", "/api/v1/snapshot", None, "viewer"),
    ("GET", "/api/v1/settings", None, "viewer"),
    ("GET", "/api/v1/ssl", None, "viewer"),
    ("GET", "/api/v1/reports/briefing", None, "viewer"),
    ("GET", "/api/v1/reports/changes", None, "viewer"),
    ("POST", "/api/v1/issues/ack", {"key": "server:0:cpu", "mode": "24h"}, "operator"),
    ("DELETE", "/api/v1/issues/ack?key=server:{sid}:cpu", None, "operator"),
    ("GET", "/api/v1/servers/{sid}/host-health", None, "viewer"),
    ("GET", "/api/v1/panel", None, "viewer"),
    ("PATCH", "/api/v1/servers/{sid}/listeners", {"proto": "tcp", "port": 22}, "admin"),
    ("PATCH", "/api/v1/servers/{sid}/ignores", {"kind": "container", "name": "x"}, "admin"),
    ("POST", "/api/v1/servers/{sid}/jobs", {"kind": "ping"}, "operator"),
    ("POST", "/api/v1/servers/{sid}/jobs", {"kind": "speedtest_down"}, "operator"),
    ("POST", "/api/v1/servers/{sid}/jobs", {"kind": "processes"}, "operator"),
    ("POST", "/api/v1/servers/{sid}/jobs", {"kind": "traceroute", "args": {"target": "1.1.1.1"}}, "operator"),
    ("POST", "/api/v1/domains/{dom}/check", None, "operator"),
    ("POST", "/api/v1/servers/{sid}/jobs", {"kind": "reboot"}, "admin"),
    ("POST", "/api/v1/servers/{sid}/jobs", {"kind": "apt_upgrade_safe"}, "admin"),
    ("POST", "/api/v1/servers/{sid}/jobs", {"kind": "self_update"}, "admin"),
    ("POST", "/api/v1/servers/{sid}/jobs", {"kind": "cert_delete", "args": {"name": "a.example.com"}}, "admin"),
    ("POST", "/api/v1/servers/{sid}/jobs", {"kind": "service_restart", "args": {"unit": "xray"}}, "admin"),
    ("POST", "/api/v1/servers/{sid}/jobs", {"kind": "vacuum_logs"}, "admin"),
    ("POST", "/api/v1/servers", {"name": "n"}, "admin"),
    ("PATCH", "/api/v1/servers/{sid}", {"alias": "x"}, "admin"),
    ("PATCH", "/api/v1/servers/{sid}", {"count_upload": False}, "admin"),
    ("DELETE", "/api/v1/servers/{sid}", None, "admin"),
    ("POST", "/api/v1/servers/{sid}/enroll-token", None, "admin"),
    ("POST", "/api/v1/categories", {"name": "new-cat"}, "admin"),
    ("PATCH", "/api/v1/categories/{cat}", {"name": "renamed"}, "admin"),
    ("DELETE", "/api/v1/categories/{cat}", None, "admin"),
    ("PUT", "/api/v1/settings", {"cpu_warn": 80}, "admin"),
    ("POST", "/api/v1/domains", {"host": "new.example.com"}, "admin"),
    ("DELETE", "/api/v1/domains/{dom}", None, "admin"),
    ("GET", "/api/v1/telegram/channels", None, "admin"),
    ("POST", "/api/v1/telegram/channels", {"name": "n", "chat_id": "-1007777777777"}, "admin"),
    ("DELETE", "/api/v1/telegram/channels/{chan}", None, "admin"),
    ("POST", "/api/v1/telegram/channels/{chan}/test", None, "admin"),
    ("GET", "/api/v1/telegram/routes", None, "admin"),
    ("PUT", "/api/v1/telegram/routes", {"cpu": "admins"}, "admin"),
    ("GET", "/api/v1/keys", None, "owner"),
    ("POST", "/api/v1/keys", {"name": "k", "scope": "read"}, "owner"),
    ("DELETE", "/api/v1/keys/{key}", None, "owner"),
    ("GET", "/api/v1/members", None, "owner"),
    ("POST", "/api/v1/members", {"tg_id": 555, "role": "viewer"}, "owner"),
]


@pytest.mark.parametrize("method,path,body,least", MATRIX, ids=["%s %s %s" % (m, p, (b or {}).get("kind", "")) for m, p, b, _ in MATRIX])
def test_role_matrix(team, method, path, body, least):
    for role in ("viewer", "operator", "admin", "owner"):
        ids = _fresh(team["owner"])
        r = team[role].request(method, path.format(**ids), json=body)
        if RANK[role] < RANK[least]:
            assert r.status_code == 403 and r.json()["code"] == "auth.forbidden", (role, r.status_code, r.text[:200])
        else:
            assert r.status_code not in (401, 403) and r.status_code < 500, (role, r.status_code, r.text[:200])


def test_member_patch_and_delete_are_owner_only(team):
    target = invite(team["owner"], 556, "viewer")
    for role in ("viewer", "operator", "admin"):
        assert team[role].patch("/api/v1/members/%d" % target, json={"role": "admin"}).json()["code"] == "auth.forbidden"
        assert team[role].delete("/api/v1/members/%d" % target).json()["code"] == "auth.forbidden"
    assert team["owner"].patch("/api/v1/members/%d" % target, json={"role": "operator"}).json()["role"] == "operator"
    assert team["owner"].delete("/api/v1/members/%d" % target).status_code == 204


def test_an_operator_s_check_is_queued_but_a_reboot_is_not(team):
    sid, _ = make_server(team["owner"], "op-1")
    op = team["operator"]
    assert op.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "ping"}).status_code == 201
    assert op.post("/api/v1/servers/%d/jobs" % sid, json={"kind": "reboot"}).status_code == 403
    kinds = [j["kind"] for j in team["owner"].get("/api/v1/servers/%d/jobs" % sid).json()]
    assert kinds == ["ping"]


def test_keys_cannot_manage_members_or_switch(owner):
    full = owner.post("/api/v1/keys", json={"name": "f", "scope": "full"}).json()["token"]
    h = {"Authorization": "Bearer " + full}
    owner.cookies.clear()
    assert owner.get("/api/v1/members", headers=h).json()["code"] == "auth.forbidden"
    assert owner.post("/api/v1/members", json={"tg_id": 5, "role": "admin"}, headers=h).json()["code"] == "auth.forbidden"
    assert owner.post("/api/v1/auth/workspace", json={"workspace_id": 1}, headers=h).json()["code"] == "auth.forbidden"
    assert owner.get("/api/v1/auth/workspaces", headers=h).json()["code"] == "auth.forbidden"
