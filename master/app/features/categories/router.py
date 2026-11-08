import sqlite3
import time
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...db import get_db
from ...deps import Actor, current_workspace, require
from ...errors import DLError

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryBody(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class CategoryOut(BaseModel):
    id: int
    name: str
    server_count: int


def _out(db: sqlite3.Connection, ws: int, category_id: int) -> dict:
    row = db.execute(
        "SELECT c.id, c.name, (SELECT COUNT(*) FROM servers s WHERE s.category_id=c.id AND s.workspace_id=c.workspace_id) AS server_count "
        "FROM categories c WHERE c.id=? AND c.workspace_id=?",
        (category_id, ws),
    ).fetchone()
    if not row:
        raise DLError("category.not_found")
    return dict(row)


def _unique(db: sqlite3.Connection, ws: int, name: str, except_id: int = 0) -> str:
    name = name.strip()
    if not name:
        raise DLError("category.invalid")
    if db.execute("SELECT 1 FROM categories WHERE workspace_id=? AND name=? AND id<>?", (ws, name, except_id)).fetchone():
        raise DLError("category.exists")
    return name


@router.get("", response_model=List[CategoryOut], operation_id="categories_list")
def list_categories(_: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT c.id, c.name, (SELECT COUNT(*) FROM servers s WHERE s.category_id=c.id AND s.workspace_id=c.workspace_id) AS server_count "
        "FROM categories c WHERE c.workspace_id=? ORDER BY c.id",
        (ws,),
    )
    return [dict(r) for r in rows]


@router.post("", response_model=CategoryOut, status_code=201, operation_id="categories_create")
def create_category(body: CategoryBody, _: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
                    db: sqlite3.Connection = Depends(get_db)):
    name = _unique(db, ws, body.name)
    cur = db.execute("INSERT INTO categories (workspace_id, name, created_at) VALUES (?,?,?)", (ws, name, int(time.time())))
    return _out(db, ws, cur.lastrowid)


@router.patch("/{category_id}", response_model=CategoryOut, operation_id="categories_update")
def update_category(category_id: int, body: CategoryBody, _: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
                    db: sqlite3.Connection = Depends(get_db)):
    _out(db, ws, category_id)
    db.execute("UPDATE categories SET name=? WHERE id=? AND workspace_id=?", (_unique(db, ws, body.name, category_id), category_id, ws))
    return _out(db, ws, category_id)


@router.delete("/{category_id}", status_code=204, operation_id="categories_delete")
def delete_category(category_id: int, _: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
                    db: sqlite3.Connection = Depends(get_db)):
    _out(db, ws, category_id)
    db.execute("DELETE FROM categories WHERE id=? AND workspace_id=?", (category_id, ws))  # its servers fall back to no category
