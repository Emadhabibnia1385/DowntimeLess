"""Migration 014 on a database at 013 with rows in every table: nothing lost, everything in workspace 1, same behaviour."""
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import settings as settings_mod
from app.db import migrate

MIGRATIONS = Path(__file__).resolve().parents[1] / "app" / "migrations"

SEED = [
    "INSERT INTO users (id, tg_id, tg_username, name, role, username, password_hash, created_at) VALUES (1, 111, 'emad', 'Emad', 'owner', 'emad', NULL, 10)",
    "INSERT INTO users (id, tg_id, tg_username, name, role, created_at) VALUES (2, 222, 'adm', 'Admin', 'admin', 11)",
    "INSERT INTO users (id, tg_id, tg_username, name, role, created_at) VALUES (3, 333, NULL, 'View', 'viewer', 12)",
    "INSERT INTO sessions (id, user_id, token_hash, ip, ua, created_at, expires_at) VALUES (1, 2, 'sess', '1.2.3.4', 'ua', 50, 9999999999)",
    "INSERT INTO login_challenges (token_hash, poll_hash, status, user_id, created_at, expires_at) VALUES ('t', 'p', 'approved', 1, 1, 2)",
    "INSERT INTO claims (token_hash, created_at, used_at) VALUES ('c', 1, 2)",
    "INSERT INTO categories (id, name, created_at) VALUES (7, 'ویژه', 1)",
    "INSERT INTO servers (id, name, alias, role, permission, agent_hash, public_ip, last_seen, created_at, category_id, acct_on, quota_gb) "
    "VALUES (5, 'de-1', 'آلمان', 'exit', 'full', 'agenthash', '198.51.100.1', 100, 1, 7, 1, 500)",
    "INSERT INTO servers (id, name, role, permission, created_at) VALUES (6, 'ir-1', 'relay', 'full', 1)",
    "INSERT INTO metrics (server_id, ts, cpu, rx_delta, tx_delta) VALUES (5, 100, 12.5, 10, 20)",
    "INSERT INTO pings (server_id, ts, target, loss, rtt) VALUES (6, 100, '198.51.100.1', 0, 40)",
    "INSERT INTO jobs (id, server_id, kind, args, status, created_by, created_at) VALUES (9, 5, 'ping', '{}', 'ok', 1, 100)",
    "INSERT INTO settings (key, value) VALUES ('cpu_warn', '77'), ('on_cpu', '0')",
    "INSERT INTO api_keys (id, name, prefix, token_hash, scope, created_by, created_at) VALUES (4, 'bot', 'dl_abcd', 'keyhash', 'full', 1, 1)",
    "INSERT INTO domains (id, host, port, note, created_at, source, server_id, seen_at, ignored, not_after) "
    "VALUES (3, 'panel.example.com', 443, 'note', 1, 'auto', 5, 90, 1, 12345)",
    "INSERT INTO alert_state (key, level) VALUES ('ssl:d3', 'warning')",
    "INSERT INTO incidents (id, key, code, server_id, server_name, severity, title, evidence, opened_at, last_seen, notified_at) "
    "VALUES (8, 'server:5:disk', 'disk', 5, 'de-1', 'critical', 'دیسک', '{}', 10, 20, 15)",
    "INSERT INTO link_traffic (server_id, peer_ip, hour, in_bytes, out_bytes) VALUES (6, '198.51.100.1', 3600, 1, 2)",
    "INSERT INTO link_prev (server_id, peer_ip, in_bytes, out_bytes) VALUES (6, '198.51.100.1', 1, 2)",
    "INSERT INTO telegram_channels (id, name, chat_id, created_at) VALUES (2, 'هشدار', '-1001234567890', 1)",
    "INSERT INTO rule_routes (rule, route) VALUES ('cpu', 'channel:2')",
    "INSERT INTO flapping (key, since) VALUES ('server:5:cpu', 30)",
    "INSERT INTO events (id, ts, server_id, kind, title, detail) VALUES (11, 100, 5, 'rebooted', 'de-1: rebooted', '{}')",
]
TABLES = ("users", "sessions", "login_challenges", "claims", "categories", "servers", "metrics", "pings", "jobs", "settings",
          "api_keys", "domains", "alert_state", "incidents", "link_traffic", "link_prev", "telegram_channels", "rule_routes",
          "flapping", "events")


def _at_013(path, applied_after=()):
    """A database as production has it: every migration up to 013 and, optionally, later ones (015) already recorded."""
    db = sqlite3.connect(path, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("CREATE TABLE schema_migrations (name TEXT PRIMARY KEY)")
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name < "014":
            db.executescript(f.read_text(encoding="utf-8"))
            db.execute("INSERT INTO schema_migrations VALUES (?)", (f.name,))
    db.execute("DELETE FROM categories")  # 005 seeds three; this fleet uses its own
    for sql in SEED:
        db.execute(sql)
    for name in applied_after:
        db.executescript((MIGRATIONS / name).read_text(encoding="utf-8"))
        db.execute("INSERT INTO schema_migrations VALUES (?)", (name,))
    return db


def _rows(db, table, drop=()):
    cols = [r["name"] for r in db.execute("PRAGMA table_info(%s)" % table) if r["name"] not in drop]
    return sorted(tuple(r) for r in db.execute("SELECT %s FROM %s" % (", ".join(cols), table))), cols


@pytest.fixture(params=[(), ("015_acct_default.sql",)], ids=["at-013", "013-and-015-recorded"])
def migrated(tmp_path, request):
    db = _at_013(tmp_path / "downtimeless.db", request.param)
    before = {t: _rows(db, t) for t in TABLES}
    assert all(before[t][0] for t in TABLES), [t for t in TABLES if not before[t][0]]  # every table really has a row
    migrate(db)
    yield db, before
    db.close()


def test_every_row_survives_with_the_same_values(migrated):
    db, before = migrated
    for table in TABLES:
        old_rows, old_cols = before[table]
        new_rows, _ = _rows(db, table, drop=())
        keep = [c for c in old_cols if not (table == "servers" and c == "acct_on")]  # 015 switches counting on
        old_rows = sorted(tuple(r[old_cols.index(c)] for c in keep) for r in old_rows)
        got = sorted(tuple(r) for r in db.execute("SELECT %s FROM %s" % (", ".join(keep), table)))
        assert got == old_rows, table
        assert len(new_rows) == len(old_rows), table


def test_everything_lands_in_workspace_1_owned_by_the_owner(migrated):
    db, _ = migrated
    assert tuple(tuple(r) for r in db.execute("SELECT id, name, owner_user_id FROM workspaces")) == ((1, "فضای کار اصلی", 1),)
    members = [tuple(r) for r in db.execute("SELECT workspace_id, user_id, role FROM workspace_members ORDER BY user_id")]
    assert members == [(1, 1, "owner"), (1, 2, "admin"), (1, 3, "viewer")]
    for table in ("servers", "categories", "domains", "settings", "api_keys", "telegram_channels", "rule_routes", "incidents",
                  "events", "alert_state", "flapping"):
        assert {r[0] for r in db.execute("SELECT workspace_id FROM %s" % table)} == {1}, table
    assert db.execute("SELECT active_workspace_id FROM sessions").fetchone()[0] is None
    assert db.execute("SELECT last_login_at FROM users WHERE id=2").fetchone()[0] == 50
    assert list(db.execute("PRAGMA foreign_key_check")) == []
    assert db.execute("SELECT servers.category_id FROM servers WHERE id=5").fetchone()[0] == 7  # the rebuild cascaded nothing
    assert db.execute("SELECT COUNT(*) FROM domains WHERE server_id=5").fetchone()[0] == 1


def test_keys_are_per_workspace_now(migrated):
    db, _ = migrated
    db.execute("INSERT INTO workspaces (id, name, owner_user_id, created_at) VALUES (2, 'b', 2, 1)")
    db.execute("INSERT INTO settings (workspace_id, key, value) VALUES (2, 'cpu_warn', '10')")
    db.execute("INSERT INTO categories (workspace_id, name, created_at) VALUES (2, 'ویژه', 1)")
    db.execute("INSERT INTO domains (workspace_id, host, port, created_at) VALUES (2, 'panel.example.com', 443, 1)")
    db.execute("INSERT INTO telegram_channels (workspace_id, name, chat_id, created_at) VALUES (2, 'x', '-1001234567890', 1)")
    db.execute("INSERT INTO rule_routes (workspace_id, rule, route) VALUES (2, 'cpu', 'admins')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO settings (workspace_id, key, value) VALUES (1, 'cpu_warn', '1')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO workspace_members (workspace_id, user_id, role, created_at) VALUES (1, 2, 'god', 1)")
    db.execute("INSERT INTO users (tg_id, name, role, created_at) VALUES (444, '', 'none', 1)")


def test_migrating_twice_changes_nothing(migrated):
    db, _ = migrated
    snap = {t: _rows(db, t) for t in TABLES + ("workspaces", "workspace_members")}
    migrate(db)
    assert {t: _rows(db, t) for t in snap} == snap


def test_the_existing_owner_sees_the_same_panel_after_the_upgrade(tmp_path, monkeypatch, tg):
    from app import bot, ratelimit
    from app.main import create_app

    _at_013(tmp_path / "downtimeless.db").close()
    monkeypatch.setenv("DL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DL_FRONTEND_DIR", str(tmp_path / "none"))
    settings_mod._settings = None
    ratelimit._hits.clear()
    with TestClient(create_app()) as c:
        c.app.state.bot_username = "testbot"
        start = c.post("/api/v1/auth/telegram/start").json()
        bot.handle(tg, {"update_id": 1, "message": {"from": {"id": 111}, "chat": {"id": 111}, "text": "/start wl_" + start["deep_link"].split("wl_")[1]}})
        bot.handle(tg, {"update_id": 2, "callback_query": {"id": "x", "from": {"id": 111}, "data": "wl:ok:%d" % start["challenge_id"]}})
        assert c.post("/api/v1/auth/telegram/poll", json={"challenge_id": start["challenge_id"], "poll_secret": start["poll_secret"]}).json()["status"] == "approved"
        me = c.get("/api/v1/auth/me").json()
        assert me["role"] == "owner" and me["workspace"] == {"id": 1, "name": "فضای کار اصلی", "role": "owner", "is_personal": True}
        assert c.get("/api/v1/auth/workspaces").json() == [me["workspace"]]  # no second, empty workspace for the owner
        assert sorted(s["name"] for s in c.get("/api/v1/servers").json()) == ["de-1", "ir-1"]
        assert c.get("/api/v1/settings").json()["cpu_warn"] == 77 and c.get("/api/v1/settings").json()["on_cpu"] == 0
        assert [k["name"] for k in c.get("/api/v1/keys").json()] == ["bot"]
        assert [ch["chat_id"] for ch in c.get("/api/v1/telegram/channels").json()] == ["-1001234567890"]
        assert c.get("/api/v1/telegram/routes").json()["cpu"] == "channel:2"
        assert [x["name"] for x in c.get("/api/v1/categories").json()] == ["ویژه"]
        assert [e["title"] for e in c.get("/api/v1/reports/changes?since=0&until=200").json()["events"]] == ["de-1: rebooted"]
        assert c.get("/api/v1/issues/history?range=30d").status_code == 200
        assert [m["role"] for m in c.get("/api/v1/members").json()] == ["owner", "admin", "viewer"]
        # a session from before the upgrade (no workspace stored) lands in workspace 1 on its next request
        old = TestClient(c.app)
        from app.security import digest
        import sqlite3 as _s
        raw = _s.connect(tmp_path / "downtimeless.db")
        raw.execute("UPDATE sessions SET token_hash=? WHERE id=1", (digest("old-session"),))
        raw.commit()
        raw.close()
        old.cookies.set("dl_session", "old-session")
        assert old.get("/api/v1/auth/me").json()["workspace"]["id"] == 1
        assert old.get("/api/v1/auth/me").json()["role"] == "admin"
    settings_mod._settings = None


def test_pending_migrations_run_in_name_order_only_when_not_recorded(migrated):
    db, _ = migrated
    names = [r[0] for r in db.execute("SELECT name FROM schema_migrations ORDER BY name")]
    assert names[-3:] == ["013_events.sql", "014_workspaces.sql", "015_acct_default.sql"]
    # whether 015 ran before 014 (production) or after it (fresh), every server ends with counting on
    assert {r[0] for r in db.execute("SELECT acct_on FROM servers")} == {1}
    assert {r[0] for r in db.execute("SELECT workspace_id FROM servers")} == {1}


def test_the_dry_run_script_reports_counts_and_leaves_the_given_file_alone(tmp_path, capsys):
    import hashlib
    import importlib.util

    path = tmp_path / "copy.db"
    _at_013(path, ("015_acct_default.sql",)).close()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    spec = importlib.util.spec_from_file_location("check_migration", Path(__file__).resolve().parents[1] / "scripts" / "check_migration.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(str(path)) == 0
    out = capsys.readouterr().out
    assert "pending: 014_workspaces.sql" in out and "RESULT: OK" in out and "workspace_members" in out
    assert "keyhash" not in out and "agenthash" not in out
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
