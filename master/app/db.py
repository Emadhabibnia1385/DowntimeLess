import sqlite3
from pathlib import Path
from typing import Iterator

from .settings import get_settings

MIGRATIONS = Path(__file__).parent / "migrations"


def connect() -> sqlite3.Connection:
    path = get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    # FastAPI runs a dependency and its handler on different worker threads
    db = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def migrate(db: sqlite3.Connection) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)")
    done = {r["name"] for r in db.execute("SELECT name FROM schema_migrations")}
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name in done:
            continue
        db.executescript("BEGIN;\n" + f.read_text(encoding="utf-8") + "\nINSERT INTO schema_migrations VALUES ('" + f.name + "');\nCOMMIT;")


def get_db() -> Iterator[sqlite3.Connection]:
    db = connect()
    try:
        yield db
    finally:
        db.close()
