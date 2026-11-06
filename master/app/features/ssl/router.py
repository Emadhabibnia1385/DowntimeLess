import sqlite3
import time
from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...db import get_db
from ...deps import Actor, require
from ...errors import DLError
from . import service as svc

router = APIRouter(tags=["ssl"])


class SslRow(BaseModel):
    key: str
    kind: str
    source: str
    server_id: Optional[int]
    server_name: Optional[str]
    name: str
    domains: List[str]
    not_after: Optional[int]
    days_left: Optional[int]
    issuer: Optional[str]
    error: Optional[str]
    auto_renew: str
    renew_failed: bool
    level: str
    checked_at: Optional[int]
    stale: bool
    note: Optional[str] = None
    id: Optional[int] = None


class DomainCreate(BaseModel):
    host: str = Field(min_length=3, max_length=253, pattern=r"^[A-Za-z0-9.-]+$")
    port: int = Field(default=443, ge=1, le=65535)
    note: str = Field(default="", max_length=120)


@router.get("/ssl", response_model=List[SslRow], operation_id="ssl_list")
def list_ssl(_: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)) -> Any:
    return svc.rows(db)


@router.post("/domains", response_model=SslRow, status_code=201, operation_id="ssl_add_domain")
def add_domain(body: DomainCreate, _: Actor = Depends(require("admin")), db: sqlite3.Connection = Depends(get_db)) -> Any:
    host = body.host.lower().strip(".")
    if not svc.is_public_host(host):
        raise DLError("domain.invalid")
    try:
        cur = db.execute("INSERT INTO domains (host, port, note, created_at) VALUES (?,?,?,?)", (host, body.port, body.note, int(time.time())))
    except sqlite3.IntegrityError:
        raise DLError("domain.exists")
    svc.probe_due(db, force_id=cur.lastrowid)
    return next(r for r in svc.rows(db) if r["key"] == "d%d" % cur.lastrowid)


@router.post("/domains/{domain_id}/check", response_model=SslRow, operation_id="ssl_check_domain")
def check_domain(domain_id: int, _: Actor = Depends(require("admin")), db: sqlite3.Connection = Depends(get_db)) -> Any:
    if not db.execute("SELECT 1 FROM domains WHERE id=?", (domain_id,)).fetchone():
        raise DLError("domain.not_found")
    svc.probe_due(db, force_id=domain_id)
    return next(r for r in svc.rows(db) if r["key"] == "d%d" % domain_id)


@router.delete("/domains/{domain_id}", status_code=204, operation_id="ssl_delete_domain")
def delete_domain(domain_id: int, _: Actor = Depends(require("admin")), db: sqlite3.Connection = Depends(get_db)) -> None:
    if not db.execute("DELETE FROM domains WHERE id=?", (domain_id,)).rowcount:
        raise DLError("domain.not_found")
