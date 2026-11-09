"""Operator change notes: POST /api/v1/changes writes a `note` into the change log the briefing and the Issues tab read."""
from conftest import make_server


def test_a_note_lands_in_the_change_log_and_the_briefing(owner):
    sid, _ = make_server(owner, "arno", "relay")
    r = owner.post("/api/v1/changes", json={"text": "  Arno   DNAT changed\nto DE2 ", "server_id": sid})
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["kind"] == "note" and ev["title"] == "Arno DNAT changed to DE2" and ev["server"] == "arno"
    assert ev["detail"]["text"] == "Arno DNAT changed to DE2" and ev["detail"]["via"] == "session"
    log = owner.get("/api/v1/reports/changes?kind=note").json()["events"]
    assert [e["title"] for e in log] == ["Arno DNAT changed to DE2"]
    brief = owner.get("/api/v1/reports/briefing").json()["changes_24h"]
    assert {"kind": "note", "server": "arno", "title": "Arno DNAT changed to DE2"}.items() <= brief[0].items()


def test_a_long_note_keeps_its_text_and_notes_are_not_crowded_out(owner):
    text = "x" * 500
    ev = owner.post("/api/v1/changes", json={"text": text}).json()
    assert len(ev["title"]) == 200 and ev["detail"]["text"] == text
    sid, _ = make_server(owner, "s", "exit")
    for k in range(20):
        owner.patch("/api/v1/servers/%d" % sid, json={"alias": "a%d" % k})
    kinds = [c["kind"] for c in owner.get("/api/v1/reports/briefing").json()["changes_24h"]]
    assert "note" in kinds and len(owner.get("/api/v1/reports/briefing").json()["changes_24h"][-1]["title"]) <= 500


def test_bad_notes_are_refused(owner):
    assert owner.post("/api/v1/changes", json={"text": ""}).status_code == 422
    assert owner.post("/api/v1/changes", json={"text": "   "}).status_code == 422
    assert owner.post("/api/v1/changes", json={"text": "y" * 501}).status_code == 422
    assert owner.post("/api/v1/changes", json={"text": "ok", "server_id": 99999}).status_code == 404


def test_a_full_api_key_may_write_a_note_and_a_read_key_may_not(owner, client):
    full = owner.post("/api/v1/keys", json={"name": "ai", "scope": "full"}).json()["token"]
    read = owner.post("/api/v1/keys", json={"name": "ro", "scope": "read"}).json()["token"]
    r = client.post("/api/v1/changes", json={"text": "by key"}, headers={"Authorization": "Bearer " + full})
    assert r.status_code == 201 and r.json()["detail"]["via"] == "key"
    assert client.post("/api/v1/changes", json={"text": "no"}, headers={"Authorization": "Bearer " + read}).status_code == 403
