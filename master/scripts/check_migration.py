"""Dry-run the pending migrations on a copy of a real database and show what they change.

Usage (from master/):  venv/bin/python scripts/check_migration.py /path/to/COPY-of-downtimeless.db

The given file is opened read-only and copied (SQLite backup API, so a WAL file is included) into a temporary
directory; the migrations run only on that temporary copy, which is deleted afterwards. Only names and counts are
printed, never a row's content, so no token hash, key or name leaves the database.
Exit code: 0 when nothing was lost and no new foreign key problem appeared, 1 otherwise.
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import MIGRATIONS, migrate  # noqa: E402

# tables a migration may only add rows to, never lose them from
KEEP = ("users", "sessions", "servers", "metrics", "pings", "jobs", "settings", "api_keys", "domains", "alert_state",
        "categories", "incidents", "link_traffic", "link_prev", "telegram_channels", "rule_routes", "flapping", "events")


def counts(db):
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {t: db.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0] for t in tables}


def fk_problems(db):
    return [tuple(r) for r in db.execute("PRAGMA foreign_key_check")]


def main(source: str) -> int:
    src = Path(source)
    if not src.is_file():
        print("no such file: %s" % src)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "copy.db"
        ro = sqlite3.connect("file:%s?mode=ro" % src, uri=True)
        dst = sqlite3.connect(copy)
        ro.backup(dst)
        ro.close()
        dst.close()
        db = sqlite3.connect(copy, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        done = {r[0] for r in db.execute("SELECT name FROM schema_migrations")} if "schema_migrations" in counts(db) else set()
        pending = [f.name for f in sorted(MIGRATIONS.glob("*.sql")) if f.name not in done]
        print("recorded migrations: %d, pending: %s" % (len(done), ", ".join(pending) or "none"))
        before, fk_before = counts(db), fk_problems(db)
        print("integrity before: %s" % db.execute("PRAGMA integrity_check").fetchone()[0])
        migrate(db)
        after, fk_after = counts(db), fk_problems(db)
        print("integrity after:  %s" % db.execute("PRAGMA integrity_check").fetchone()[0])
        print("\n%-22s %10s %10s" % ("table", "before", "after"))
        for t in sorted(set(before) | set(after)):
            mark = "  LOST ROWS" if t in KEEP and after.get(t, 0) < before.get(t, 0) else ""
            print("%-22s %10s %10s%s" % (t, before.get(t, "-"), after.get(t, "-"), mark))
        print("\nforeign_key_check before: %d row(s), after: %d row(s)" % (len(fk_before), len(fk_after)))
        new = sorted(set(fk_after) - set(fk_before))
        for table, rowid, parent, fkid in new[:50]:
            print("  new problem: %s rowid=%s -> %s (fk %s)" % (table, rowid, parent, fkid))
        cols = {t: [c[1] for c in db.execute('PRAGMA table_info("%s")' % t)] for t in after}
        spread = {t: [tuple(r) for r in db.execute('SELECT workspace_id, COUNT(*) FROM "%s" GROUP BY workspace_id' % t)]
                  for t in sorted(after) if "workspace_id" in cols[t]}
        if spread:
            print("\nrows per workspace_id:")
            for t, rows in spread.items():
                print("  %-20s %s" % (t, ", ".join("ws %s: %s" % r for r in rows) or "empty"))
        if "workspaces" in after:
            ws = db.execute("SELECT id, owner_user_id IS NOT NULL AS owned FROM workspaces ORDER BY id").fetchall()
            print("\nworkspaces: %s" % ", ".join("%d%s" % (r["id"], " (owned)" if r["owned"] else " (no owner)") for r in ws))
            print("members per role: %s" % ", ".join(
                "%s=%d" % tuple(r) for r in db.execute("SELECT role, COUNT(*) FROM workspace_members GROUP BY role ORDER BY role")))
        db.close()
        lost = [t for t in KEEP if after.get(t, 0) < before.get(t, 0)]
        ok = not lost and not new
        print("\nRESULT: %s" % ("OK" if ok else "PROBLEM (lost rows in %s, %d new foreign key problems)" % (lost, len(new))))
        return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
