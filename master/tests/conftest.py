import time

import pytest
from fastapi.testclient import TestClient

from app import settings as settings_mod
from app.db import connect


class FakeTelegram:
    def __init__(self):
        self.sent = []
        self.threads = []
        self.refuse = False  # a bot that is not allowed to post: send() answers False

    def send(self, chat_id, text, buttons=None, thread=None):
        if self.refuse:
            return False
        self.sent.append((chat_id, text, buttons))
        self.threads.append(thread)
        return True

    def edit(self, *a, **k):
        pass

    def answer(self, *a, **k):
        pass


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DL_FRONTEND_DIR", str(tmp_path / "none"))
    settings_mod._settings = None
    from app import ratelimit
    from app.main import create_app

    ratelimit._hits.clear()

    with TestClient(create_app()) as c:
        c.app.state.bot_username = "testbot"
        yield c
    settings_mod._settings = None


@pytest.fixture
def tg():
    return FakeTelegram()


def add_user(tg_id=111, role="owner", name="Emad", ws=1):
    """A user who is a member of workspace `ws` (the owner of workspace 1 by default)."""
    db = connect()
    now = int(time.time())
    uid = db.execute("INSERT INTO users (tg_id, name, role, created_at) VALUES (?,?,?,?)",
                     (tg_id, name, role if role in ("owner", "admin", "viewer") else "none", now)).lastrowid
    if role == "owner":
        db.execute("UPDATE workspaces SET owner_user_id=? WHERE id=? AND owner_user_id IS NULL", (uid, ws))
    db.execute("INSERT INTO workspace_members (workspace_id, user_id, role, created_at) VALUES (?,?,?,?)", (ws, uid, role, now))
    db.close()
    return uid


@pytest.fixture
def owner(client, tg):
    """Sign the client in as owner through the real Telegram challenge flow."""
    from app import bot

    add_user()
    start = client.post("/api/v1/auth/telegram/start").json()
    token = start["deep_link"].split("wl_")[1]
    bot.handle(tg, {"update_id": 1, "message": {"from": {"id": 111}, "chat": {"id": 111}, "text": "/start wl_" + token}})
    cid = start["challenge_id"]
    bot.handle(tg, {"update_id": 2, "callback_query": {"id": "x", "from": {"id": 111}, "data": "wl:ok:%d" % cid}})
    r = client.post("/api/v1/auth/telegram/poll", json={"challenge_id": cid, "poll_secret": start["poll_secret"]})
    assert r.json()["status"] == "approved"
    return client


def make_server(client, name="de-1", role="exit"):
    r = client.post("/api/v1/servers", json={"name": name, "role": role})
    assert r.status_code == 201, r.text
    token = r.json()["install_command"].split("--token ")[1]
    key = client.post("/api/agent/v1/enroll", json={"token": token, "hostname": name}).json()["agent_key"]
    return r.json()["server"]["id"], key


def report(client, key, **over):
    body = {"agent_version": "0.1.0", "hostname": "x", "cpu_pct": 5.0, "ram_total_mb": 1000, "ram_avail_mb": 800,
            "disk_total_gb": 100, "disk_used_gb": 20, "net": {"iface": "eth0", "rx_bytes": 1000, "tx_bytes": 2000, "rx_bps": 1, "tx_bps": 2}}
    body.update(over)
    return client.post("/api/agent/v1/report", json=body, headers={"X-Agent-Key": key})
