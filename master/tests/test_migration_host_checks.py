"""Migration 016 on a database at 015 with rows in every table: nothing lost, the four check tables added and scoped."""
import sqlite3

import pytest

from app.db import migrate
from test_migration_workspaces import MIGRATIONS, TABLES, _at_013, _rows


def _at_015(path):
    """Production today: everything up to 015 recorded (014 runs with foreign keys off, as the runner does)."""
    db = _at_013(path)
    db.execute("PRAGMA foreign_keys=OFF")
    for name in ("014_workspaces.sql", "015_acct_default.sql"):
        db.executescript((MIGRATIONS / name).read_text(encoding="utf-8"))
        db.execute("INSERT INTO schema_migrations VALUES (?)", (name,))
    db.execute("PRAGMA foreign_keys=ON")
    return db


@pytest.fixture
def at_015(tmp_path):
    db = _at_015(tmp_path / "downtimeless.db")
    assert db.execute("SELECT MAX(name) FROM schema_migrations").fetchone()[0] == "015_acct_default.sql"
    yield db
    db.close()


def test_016_keeps_every_row_and_adds_the_check_tables(at_015):
    db = at_015
    before = {t: _rows(db, t)[0] for t in TABLES}
    assert all(before.values())
    migrate(db)
    assert "016_host_checks.sql" in [r[0] for r in db.execute("SELECT name FROM schema_migrations")]
    for t in TABLES:
        assert _rows(db, t)[0] == before[t], t
    for t in ("listener_baseline", "check_state", "check_ignores", "node_usage"):
        cols = [r[1] for r in db.execute("PRAGMA table_info(%s)" % t)]
        assert cols[:2] == ["workspace_id", "server_id"], t
    assert list(db.execute("PRAGMA foreign_key_check")) == []
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_016_rows_follow_their_server_and_refuse_unknown_kinds(at_015):
    db = at_015
    migrate(db)
    db.execute("INSERT INTO listener_baseline (workspace_id, server_id, proto, port, first_seen, last_seen) VALUES (1, 5, 'tcp', 443, 1, 2)")
    db.execute("INSERT INTO check_state (workspace_id, server_id, data, updated_at) VALUES (1, 5, '{}', 1)")
    db.execute("INSERT INTO check_ignores (workspace_id, server_id, kind, name, created_at) VALUES (1, 5, 'container', 'x', 1)")
    db.execute("INSERT INTO node_usage (workspace_id, server_id, node_id, hour, users, bytes) VALUES (1, 5, 1, 3600, 3, 4)")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO check_ignores (workspace_id, server_id, kind, name, created_at) VALUES (1, 5, 'user', 'x', 1)")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO node_usage (workspace_id, server_id, node_id, hour, users, bytes) VALUES (1, 999, 1, 1, 1, 1)")
    db.execute("DELETE FROM servers WHERE id=5")
    for t in ("listener_baseline", "check_state", "check_ignores", "node_usage"):
        assert db.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] == 0, t


def test_the_dry_run_tool_passes_016(tmp_path, capsys):
    import importlib.util
    from pathlib import Path

    path = tmp_path / "copy.db"
    _at_015(path).close()
    spec = importlib.util.spec_from_file_location("check_migration", Path(__file__).resolve().parents[1] / "scripts" / "check_migration.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(str(path)) == 0
    out = capsys.readouterr().out
    assert "pending: 016_host_checks.sql" in out and "RESULT: OK" in out and "listener_baseline" in out
