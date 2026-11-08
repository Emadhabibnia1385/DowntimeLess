import sqlite3
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "app" / "migrations"


def test_migration_008_keeps_keys_and_turns_the_old_operate_scope_into_full():
    db = sqlite3.connect(":memory:")
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name < "008":
            db.executescript(f.read_text())
    db.execute("INSERT INTO api_keys (name, prefix, token_hash, scope, created_at) VALUES ('a','dl_aaaa','h1','read',1)")
    db.execute("INSERT INTO api_keys (name, prefix, token_hash, scope, created_at) VALUES ('b','dl_bbbb','h2','operate',2)")
    db.executescript((MIGRATIONS / "008_api_key_scopes.sql").read_text())
    assert [tuple(r) for r in db.execute("SELECT name, scope FROM api_keys ORDER BY id")] == [("a", "read"), ("b", "full")]
    try:
        db.execute("INSERT INTO api_keys (name, prefix, token_hash, scope, created_at) VALUES ('c','dl_cccc','h3','operate',3)")
    except sqlite3.IntegrityError:
        return
    raise AssertionError("the new table must refuse the old scope")


def test_migration_012_keeps_servers_and_incidents_and_adds_the_alert_tables():
    db = sqlite3.connect(":memory:")
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name < "012":
            db.executescript(f.read_text())
    db.execute("INSERT INTO servers (name, created_at, public_ip) VALUES ('de-1', 1, '198.51.100.1')")
    db.execute("INSERT INTO incidents (key, opened_at, last_seen) VALUES ('server:1:cpu', 5, 6)")
    db.executescript((MIGRATIONS / "012_alerts.sql").read_text())
    server = db.execute("SELECT public_ip, rebooted_at, prev_ip, ip_changed_at, resized_at, quota_gb, quota_reset_day FROM servers").fetchone()
    assert server == ("198.51.100.1", None, None, None, None, None, None)
    assert db.execute("SELECT key, notified_at FROM incidents").fetchone() == ("server:1:cpu", None)
    db.execute("INSERT INTO telegram_channels (name, chat_id, created_at) VALUES ('c', '-100123', 1)")
    db.execute("INSERT INTO rule_routes VALUES ('cpu', 'admins')")
    db.execute("INSERT INTO flapping VALUES ('k', 1)")
