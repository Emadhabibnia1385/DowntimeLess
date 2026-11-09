"""Migration 019: forward only; existing people, workspaces, keys and memberships keep every row and value."""
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.db import migrate

MIGRATIONS = Path(__file__).resolve().parents[1] / "app" / "migrations"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_migration.py"


def _before_019(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("CREATE TABLE schema_migrations (name TEXT PRIMARY KEY)")
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name < "019" or f.name >= "020":  # a live panel has 020 and 021 already when 019 arrives
            if f.name.startswith("019"):
                continue
            db.executescript(f.read_text(encoding="utf-8"))
            db.execute("INSERT INTO schema_migrations VALUES (?)", (f.name,))
    db.execute("INSERT INTO users (id, tg_id, name, role, created_at) VALUES (1, 111, 'Owner', 'owner', 1)")
    db.execute("INSERT INTO users (id, tg_id, name, role, created_at, username, password_hash) VALUES (2, 222, 'B', 'none', 1, 'bee', 'x')")
    db.execute("UPDATE workspaces SET owner_user_id=1 WHERE id=1")
    db.execute("INSERT INTO workspaces (id, name, owner_user_id, created_at) VALUES (2, 'B', 2, 1)")
    db.execute("INSERT INTO workspace_members (workspace_id, user_id, role, created_at) VALUES (1,1,'owner',1),(1,2,'viewer',1),(2,2,'owner',1)")
    db.execute("INSERT INTO api_keys (name, prefix, token_hash, scope, created_by, created_at, workspace_id) VALUES ('k','p','h','full',2,1,2)")
    return db


def test_019_keeps_every_row_and_adds_its_tables(tmp_path):
    db = _before_019(tmp_path / "d.db")
    before = [tuple(r) for r in db.execute("SELECT * FROM workspace_members ORDER BY workspace_id, user_id")]
    migrate(db)
    assert [tuple(r) for r in db.execute("SELECT * FROM workspace_members ORDER BY workspace_id, user_id")] == before
    assert [tuple(r) for r in db.execute("SELECT id, server_cap, domain_cap FROM workspaces ORDER BY id")] == [(1, None, None), (2, None, None)]
    assert db.execute("SELECT role_cap FROM api_keys").fetchone()[0] is None
    for table in ("app_settings", "link_tokens", "workspace_invites"):
        assert db.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0] == 0
    # one person may now own two workspaces (after a merge); an open invite per username and workspace stays unique
    db.execute("INSERT INTO workspaces (name, owner_user_id, created_at) VALUES ('second', 1, 1)")
    db.execute("INSERT INTO workspace_invites (workspace_id, tg_username, role, created_at, expires_at) VALUES (1,'x','viewer',1,2)")
    try:
        db.execute("INSERT INTO workspace_invites (workspace_id, tg_username, role, created_at, expires_at) VALUES (1,'x','viewer',1,2)")
        raise AssertionError("two open invites for one username")
    except sqlite3.IntegrityError:
        pass
    try:
        db.execute("INSERT INTO workspace_invites (workspace_id, tg_username, role, created_at, expires_at) VALUES (1,'y','admin',1,2)")
        raise AssertionError("an admin invite by username")
    except sqlite3.IntegrityError:
        pass
    assert list(db.execute("PRAGMA foreign_key_check")) == []
    migrate(db)
    db.close()


def test_the_dry_run_script_passes_before_019(tmp_path):
    db = _before_019(tmp_path / "d.db")
    db.close()
    out = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "d.db")], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "019_account_linking.sql" in out.stdout and "RESULT: OK" in out.stdout
