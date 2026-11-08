"""Migration 020: count_upload is added with 1 for every existing server and nothing else changes."""
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.db import migrate

MIGRATIONS = Path(__file__).resolve().parents[1] / "app" / "migrations"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_migration.py"


def _before_020(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("CREATE TABLE schema_migrations (name TEXT PRIMARY KEY)")
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name < "020":
            db.executescript(f.read_text(encoding="utf-8"))
            db.execute("INSERT INTO schema_migrations VALUES (?)", (f.name,))
    db.execute("INSERT INTO servers (id, name, role, permission, created_at, quota_gb, quota_reset_day) VALUES (5, 'de-1', 'exit', 'full', 1, 500, 7)")
    db.execute("INSERT INTO servers (id, name, role, permission, created_at) VALUES (6, 'ir-1', 'relay', 'full', 1)")
    db.execute("INSERT INTO metrics (server_id, ts, rx_delta, tx_delta) VALUES (5, 100, 10, 20)")
    return db


def test_existing_servers_keep_their_data_and_count_upload_defaults_to_one(tmp_path):
    db = _before_020(tmp_path / "d.db")
    old = [tuple(r) for r in db.execute("SELECT id, name, role, quota_gb, quota_reset_day, workspace_id FROM servers ORDER BY id")]
    migrate(db)
    assert [tuple(r) for r in db.execute("SELECT id, name, role, quota_gb, quota_reset_day, workspace_id FROM servers ORDER BY id")] == old
    assert [tuple(r) for r in db.execute("SELECT id, count_upload FROM servers ORDER BY id")] == [(5, 1), (6, 1)]
    assert tuple(db.execute("SELECT rx_delta, tx_delta FROM metrics").fetchone()) == (10, 20)
    db.execute("INSERT INTO servers (name, created_at) VALUES ('new', 1)")
    assert db.execute("SELECT count_upload FROM servers WHERE name='new'").fetchone()[0] == 1
    assert list(db.execute("PRAGMA foreign_key_check")) == []
    migrate(db)  # a second run changes nothing
    assert db.execute("SELECT COUNT(*) FROM servers").fetchone()[0] == 3
    db.close()


def test_the_dry_run_script_reports_ok_on_a_copy(tmp_path):
    _before_020(tmp_path / "d.db").close()
    out = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "d.db")], capture_output=True, text=True)
    assert out.returncode == 0 and "RESULT: OK" in out.stdout and "020_count_upload.sql" in out.stdout, out.stdout[-600:]
