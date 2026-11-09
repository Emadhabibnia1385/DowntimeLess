"""Migration 021: two new tables for TCP probes; nothing that exists changes."""
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.db import migrate

MIGRATIONS = Path(__file__).resolve().parents[1] / "app" / "migrations"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_migration.py"


def _before_021(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("CREATE TABLE schema_migrations (name TEXT PRIMARY KEY)")
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name < "021":
            db.executescript(f.read_text(encoding="utf-8"))
            db.execute("INSERT INTO schema_migrations VALUES (?)", (f.name,))
    db.execute("INSERT INTO servers (id, name, role, permission, created_at, public_ip) VALUES (5, 'de-1', 'exit', 'full', 1, '198.51.100.1')")
    db.execute("INSERT INTO servers (id, name, role, permission, created_at) VALUES (6, 'ir-1', 'relay', 'full', 1)")
    db.execute("INSERT INTO pings (server_id, ts, target, loss, rtt) VALUES (6, 100, '198.51.100.1', 0, 40)")
    return db


def test_021_adds_the_probe_tables_and_keeps_everything_else(tmp_path):
    db = _before_021(tmp_path / "d.db")
    migrate(db)
    assert db.execute("SELECT COUNT(*) FROM pings").fetchone()[0] == 1
    db.execute("INSERT INTO probes (server_id, ts, target, port, ok) VALUES (6, 1, '198.51.100.1', 443, 1)")
    db.execute("INSERT INTO probe_ports (workspace_id, target, port, last_ok) VALUES (1, '198.51.100.1', 443, 1)")
    db.execute("DELETE FROM servers WHERE id=6")
    assert db.execute("SELECT COUNT(*) FROM probes").fetchone()[0] == 0  # a deleted relay takes its probes along
    assert list(db.execute("PRAGMA foreign_key_check")) == []
    migrate(db)
    db.close()


def test_the_dry_run_script_passes_on_a_database_before_021(tmp_path):
    db = _before_021(tmp_path / "d.db")
    db.close()
    out = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "d.db")], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "021_tcp_probes.sql" in out.stdout
