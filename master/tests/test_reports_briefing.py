import json
import re

import pytest
from seed import seed_fleet

from app.db import connect
from conftest import make_server, report

ENDPOINTS = [
    "briefing", "health", "playbooks", "playbooks/offline", "changes", "daily", "incidents", "traffic", "availability", "capacity", "relays",
]


def _read_key(owner):
    token = owner.post("/api/v1/keys", json={"name": "t", "scope": "read"}).json()["token"]
    return {"Authorization": "Bearer " + token}, token


def test_briefing_shape_and_content(owner):
    ids, _ = seed_fleet(owner)
    b = owner.get("/api/v1/reports/briefing").json()
    assert b["detail"] == "brief"
    assert b["fleet"]["total"] == 16 and (b["fleet"]["online"], b["fleet"]["offline"], b["fleet"]["pending"]) == (14, 1, 1)
    roles = {r["role"]: r for r in b["fleet"]["by_role"]}
    assert roles["relay"]["offline"] == 1 and roles["exit"]["pending"] == 1
    assert (b["issues"]["critical"], b["issues"]["warning"], b["issues"]["info"]) == (5, 8, 1)
    first = b["issues"]["items"][0]
    assert first["severity"] == "critical" and {"server", "code", "evidence", "suggestion", "title"} <= set(first)
    assert [r["code"] for r in b["recurring_24h"]] == ["cpu"] and b["recurring_24h"][0]["flapping"]
    kinds = {p["kind"]: p for p in b["path_problems"]}
    assert kinds["blacklisted"]["server"] == "de-1" and "relay_egress" in kinds
    assert b["health"]["counts"]["failing"] == 3
    assert b["traffic"]["today"]["total"] >= 0 and b["traffic"]["last_7d"]["total"] > 0 and len(b["traffic"]["top_servers"]) == 5
    assert b["quota"] == [] and any("quota" in x for x in b["not_measured"])
    assert [c["name"] for c in b["certs_at_risk"]] == ["panel.example.com"]
    assert b["changes_24h"] and b["check_first"][0]["code"] == "offline"
    assert len(b["check_first"]) <= 5 and all(s["first_check"] for s in b["check_first"][:3])


def test_briefing_markdown_is_dense_and_under_budget(owner):
    seed_fleet(owner)
    r = owner.get("/api/v1/reports/briefing?format=md")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/markdown")
    md = r.text
    for heading in ("## Check first", "## Open issues", "### critical", "## Path problems", "## Health", "## Traffic", "## Certificates at risk", "## Changes in 24h"):
        assert heading in md, heading
    assert "ir-3" in md and "conntrack_pct=91.0" in md
    assert len(md) // 4 < 2500, len(md) // 4  # tokens by the chars/4 rule, 16 servers with 12 issues
    assert "**" not in md and "```" not in md  # no decoration


def test_detail_full_lifts_caps_and_keeps_whole_suggestions(owner):
    ids, keys = seed_fleet(owner)
    brief, full = (owner.get("/api/v1/reports/briefing?detail=" + d).json() for d in ("brief", "full"))
    assert len(full["changes_24h"]) > len(brief["changes_24h"]) == 8
    # more issues than the brief cap: 20 servers with a full disk
    for n in range(20):
        sid, key = make_server(owner, "disk-%d" % n, "exit")
        report(owner, key, disk_used_gb=97)
    brief, full = (owner.get("/api/v1/reports/briefing?detail=" + d).json() for d in ("brief", "full"))
    assert len(brief["issues"]["items"]) == 15 and brief["issues"]["truncated"]
    assert len(full["issues"]["items"]) == 34 and not full["issues"]["truncated"]
    assert brief["issues"]["critical"] == full["issues"]["critical"]
    md = owner.get("/api/v1/reports/briefing?format=md").text
    assert "(list truncated" in md


def test_empty_fleet_still_answers(owner):
    md = owner.get("/api/v1/reports/briefing?format=md").text
    assert "Servers 0" in md and "No open issues" in md


@pytest.mark.parametrize("query", ["format=xml", "detail=huge", "format=md&detail=x"])
def test_bad_parameters_are_refused_with_a_registry_code(owner, query):
    r = owner.get("/api/v1/reports/briefing?" + query)
    assert r.status_code == 422 and r.json()["code"] == "report.param_invalid"


@pytest.mark.parametrize("path", ENDPOINTS)
def test_every_endpoint_needs_a_session_or_key_and_a_read_key_is_enough(owner, path):
    seed_fleet(owner)
    h, token = _read_key(owner)
    owner.cookies.clear()
    url = "/api/v1/reports/" + path
    assert owner.get(url).status_code == 401
    ok = owner.get(url, headers=h)
    assert ok.status_code == 200, ok.text
    md = owner.get(url + ("&" if "?" in url else "?") + "format=md", headers=h)
    assert md.status_code == 200 and md.headers["content-type"].startswith("text/markdown") and md.text.startswith("# ")
    assert owner.get(url + "?format=nope", headers=h).json()["code"] == "report.param_invalid"


def test_no_secret_reaches_any_report(owner):
    ids, keys = seed_fleet(owner)
    h, token = _read_key(owner)
    session = owner.cookies.get("dl_session")
    seen = ""
    for path in ENDPOINTS + ["playbooks"]:
        for fmt in ("json", "md"):
            seen += owner.get("/api/v1/reports/%s%sformat=%s" % (path, "&" if "?" in path else "?", fmt), headers=h).text
    secrets = list(keys.values()) + [token]
    if session:
        secrets.append(session)
    for secret in secrets:
        assert secret not in seen
    db = connect()
    hashes = [r[0] for r in db.execute("SELECT agent_hash FROM servers WHERE agent_hash IS NOT NULL")] + [r[0] for r in db.execute("SELECT token_hash FROM api_keys")]
    db.close()
    for value in hashes:
        assert value not in seen
    for word in ("agent_hash", "enroll_hash", "token_hash", "password_hash", "last_report"):
        assert word not in seen
    assert not re.search(r"dl_[A-Za-z0-9_-]{20,}", seen)


def test_json_and_md_describe_the_same_issues(owner):
    seed_fleet(owner)
    b = owner.get("/api/v1/reports/briefing?detail=full").json()
    md = owner.get("/api/v1/reports/briefing?format=md&detail=full").text
    for i in b["issues"]["items"]:
        assert "| %s | %s |" % (i["server"], i["code"]) in md
    assert json.dumps(b)  # plain JSON all the way


def test_llms_txt_points_an_assistant_at_the_briefing_first_and_lists_every_report(owner):
    text = owner.get("/llms.txt").text
    assert text.index("/api/v1/reports/briefing?format=md") < text.index("/api/v1/snapshot")
    assert "/api/v1/reports/playbooks/{code}" in text
    for name in ("briefing", "playbooks", "health", "changes", "daily", "incidents", "traffic", "availability", "capacity", "relays"):
        assert "/api/v1/reports/" + name in text, name
