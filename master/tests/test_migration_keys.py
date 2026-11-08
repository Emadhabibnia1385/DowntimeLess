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
