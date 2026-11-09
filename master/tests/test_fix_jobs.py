"""One-click fixes (nft_reload, sysctl_apply, ipset_sync, tunnel_restart): a closed list of kinds and arguments, a
signed-in admin only, the server's own tunnel units only, one at a time, logged when asked and when done."""
import pytest

from app.db import connect
from checks_data import checks
from conftest import make_server, report


def post(client, sid, kind, args=None, **kw):
    return client.post("/api/v1/servers/%d/jobs" % sid, json={"kind": kind, "args": args or {}}, **kw)


@pytest.mark.parametrize("kind", ["nft_reload", "sysctl_apply", "ipset_sync"])
def test_an_admin_queues_a_fix_the_agent_gets_it_and_both_ends_are_logged(owner, kind):
    sid, key = make_server(owner, "arno", "relay")
    r = post(owner, sid, kind)
    assert r.status_code == 201, r.text
    jobs = report(owner, key).json()["jobs"]
    assert [(j["kind"], j["args"]) for j in jobs] == [(kind, {})]
    report(owner, key, jobs_done=[{"id": jobs[0]["id"], "status": "ok", "result": {"output": "x"}}])
    kinds = [e["kind"] for e in owner.get("/api/v1/reports/changes").json()["events"]]
    assert kinds[:2] == ["job_done", "job_created"]


@pytest.mark.parametrize("args", [{"file": "/etc/passwd"}, {"unit": "x"}, {"cmd": "rm -rf /"}])
def test_fixes_without_arguments_refuse_any(owner, args):
    sid, _ = make_server(owner, "arno", "relay")
    for kind in ("nft_reload", "sysctl_apply", "ipset_sync"):
        r = post(owner, sid, kind, args)
        assert r.status_code == 422 and r.json()["code"] == "job.args_invalid", (kind, args)


@pytest.mark.parametrize("kind", ["nft_flush", "shell", "NFT_RELOAD", "tunnel_restart ", ""])
def test_unknown_fix_kinds_are_refused(owner, kind):
    sid, _ = make_server(owner, "arno", "relay")
    r = post(owner, sid, kind)
    assert r.status_code == 422 and r.json()["code"] == "job.kind_unknown"


TUNNELS = {"configs": [{"name": "de1", "type": "backpack", "unit": "backpack-de1.service", "ports": [], "active": "active"}], "links": []}


def test_tunnel_restart_takes_only_a_tunnel_unit_the_server_reported(owner):
    sid, key = make_server(owner, "nl-1", "exit")
    report(owner, key, agent_version="0.3.3", checks=checks(tunnels=TUNNELS))
    for unit in ("backpack-nl9.service", "nginx.service", "relay-dnat.service", "backpack-de1", "backpack-de1.service;reboot"):
        r = post(owner, sid, "tunnel_restart", {"unit": unit})
        assert r.status_code == 422, unit
    assert post(owner, sid, "tunnel_restart", {"unit": "backpack-de1.service", "x": 1}).status_code == 422
    assert post(owner, sid, "tunnel_restart", {"unit": "backhaul-de.service"}).status_code == 201  # an enabled unit of checks()
    assert post(owner, sid, "tunnel_restart", {"unit": "backpack-de1.service"}).status_code == 201


def test_a_second_fix_waits_for_the_first_and_a_read_level_server_refuses(owner):
    sid, key = make_server(owner, "arno", "relay")
    assert post(owner, sid, "nft_reload").status_code == 201
    r = post(owner, sid, "nft_reload")
    assert r.status_code == 409 and r.json()["code"] == "job.pending"
    assert post(owner, sid, "sysctl_apply").status_code == 201  # another kind is fine
    db = connect()
    db.execute("UPDATE servers SET permission='read' WHERE id=?", (sid,))
    db.close()
    r = post(owner, sid, "ipset_sync")
    assert r.status_code == 403 and r.json()["code"] == "job.permission"


def test_api_keys_never_queue_a_fix_even_full_ones(owner, client):
    sid, _ = make_server(owner, "arno", "relay")
    for scope in ("full", "read"):
        token = owner.post("/api/v1/keys", json={"name": scope, "scope": scope}).json()["token"]
        r = post(client, sid, "nft_reload", headers={"Authorization": "Bearer " + token})
        assert r.status_code == 403, scope
    db = connect()
    assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    db.close()
