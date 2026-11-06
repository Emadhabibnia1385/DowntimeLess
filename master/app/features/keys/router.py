import sqlite3
import time
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...db import get_db
from ...deps import Actor, require, session_only
from ...errors import DLError
from ...security import digest, new_token

router = APIRouter(prefix="/keys", tags=["keys"])


class KeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    scope: str = Field(pattern="^(read|operate)$")


class KeyOut(BaseModel):
    id: int
    name: str
    prefix: str
    scope: str
    created_at: int
    last_used: Optional[int]


class KeyCreated(KeyOut):
    token: str


def _owner(actor: Actor = Depends(session_only)) -> Actor:
    return require("owner")(actor)


@router.get("", response_model=List[KeyOut], operation_id="keys_list")
def list_keys(_: Actor = Depends(_owner), db: sqlite3.Connection = Depends(get_db)):
    return [dict(r) for r in db.execute("SELECT id, name, prefix, scope, created_at, last_used FROM api_keys ORDER BY id")]


@router.post("", response_model=KeyCreated, status_code=201, operation_id="keys_create")
def create_key(body: KeyCreate, actor: Actor = Depends(_owner), db: sqlite3.Connection = Depends(get_db)):
    token = "dl_" + new_token(32)
    now = int(time.time())
    cur = db.execute(
        "INSERT INTO api_keys (name, prefix, token_hash, scope, created_by, created_at) VALUES (?,?,?,?,?,?)",
        (body.name, token[:8], digest(token), body.scope, actor.user_id, now),
    )
    return {"id": cur.lastrowid, "name": body.name, "prefix": token[:8], "scope": body.scope, "created_at": now, "last_used": None, "token": token}


@router.delete("/{key_id}", status_code=204, operation_id="keys_delete")
def delete_key(key_id: int, _: Actor = Depends(_owner), db: sqlite3.Connection = Depends(get_db)):
    if not db.execute("DELETE FROM api_keys WHERE id=?", (key_id,)).rowcount:
        raise DLError("key.not_found")
