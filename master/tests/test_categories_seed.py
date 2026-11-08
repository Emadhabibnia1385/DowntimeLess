import sqlite3
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "app" / "migrations"


def _upto(name_exclusive, db):
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name < name_exclusive:
            db.executescript(f.read_text())


def test_a_fresh_install_has_no_categories(owner):
    assert owner.get("/api/v1/categories").json() == []


def test_a_new_server_counts_traffic_between_servers_by_default(owner):
    created = owner.post("/api/v1/servers", json={"name": "a", "role": "relay"}).json()["server"]
    assert created["acct_on"] is True


def test_an_old_install_keeps_only_the_fleet_labels_its_servers_used():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    _upto("005", db)
    for name, fleet in (("a", "emad"), ("b", "mobin")):
        db.execute("INSERT INTO servers (name, role, fleet, created_at) VALUES (?, 'exit', ?, 1)", (name, fleet))
    db.executescript((MIGRATIONS / "005_categories.sql").read_text())
    assert sorted(r["name"] for r in db.execute("SELECT name FROM categories")) == ["عماد", "مبین"]
    assert [r["category_id"] is not None for r in db.execute("SELECT category_id FROM servers ORDER BY id")] == [True, True]


def test_a_database_without_servers_gets_no_category_from_the_old_seed():
    db = sqlite3.connect(":memory:")
    _upto("005", db)
    db.executescript((MIGRATIONS / "005_categories.sql").read_text())
    assert db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0
