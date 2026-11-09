"""Panel-wide switches that belong to no workspace (registration_open). Only the panel owner changes them."""
import sqlite3

DEFAULTS = {"registration_open": "1"}


def get(db: sqlite3.Connection, key: str) -> str:
    row = db.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else DEFAULTS[key]


def put(db: sqlite3.Connection, key: str, value: str) -> None:
    if key not in DEFAULTS:
        raise KeyError(key)
    db.execute("INSERT INTO app_settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def registration_open(db: sqlite3.Connection) -> bool:
    """Open only when the switch is on AND the panel already has an owner (a fresh install is claimed first)."""
    owner = db.execute("SELECT owner_user_id FROM workspaces WHERE id=1").fetchone()
    return get(db, "registration_open") == "1" and owner is not None and owner["owner_user_id"] is not None
