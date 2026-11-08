import json
import re
import sqlite3
import time
from typing import List

from fastapi import APIRouter, Depends

from ...db import get_db
from ...deps import Actor, require
from ...errors import DLError
from ...security import digest, new_token
from ..reports import events as changelog
from . import service as svc
from .schemas import JobCreate, JobOut, MetricsOut, ServerCreate, ServerCreated, ServerOut, ServerPatch

router = APIRouter(prefix="/servers", tags=["servers"])


def _category(db: sqlite3.Connection, category_id):
    if category_id is not None and not db.execute("SELECT 1 FROM categories WHERE id=?", (category_id,)).fetchone():
        raise DLError("category.not_found")
    return category_id


def _row(db: sqlite3.Connection, server_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()
    if not row:
        raise DLError("server.not_found")
    return row


@router.get("", response_model=List[ServerOut], operation_id="servers_list")
def list_servers(_: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)):
    return [svc.server_out(r) for r in db.execute("SELECT * FROM servers ORDER BY role, name")]


@router.post("", response_model=ServerCreated, status_code=201, operation_id="servers_create")
def create_server(body: ServerCreate, _: Actor = Depends(require("admin")), db: sqlite3.Connection = Depends(get_db)):
    token = new_token(24)
    cols = svc.role_columns(body.role)
    cur = db.execute(
        "INSERT INTO servers (name, alias, role, panel_only, category_id, enroll_hash, created_at, permission) VALUES (?,?,?,?,?,?,?,'full')",
        (body.name, body.alias, cols["role"], cols["panel_only"], _category(db, body.category_id), digest(token), int(time.time())),
    )
    changelog.record(db, "server_added", "%s (%s)" % (body.name, body.role), cur.lastrowid, {"role": body.role})
    return {"server": svc.server_out(_row(db, cur.lastrowid)), "install_command": svc.install_command(token)}


@router.post("/{server_id}/enroll-token", response_model=ServerCreated, operation_id="servers_new_enroll_token")
def new_enroll_token(server_id: int, _: Actor = Depends(require("admin")), db: sqlite3.Connection = Depends(get_db)):
    row = _row(db, server_id)
    token = new_token(24)
    db.execute("UPDATE servers SET enroll_hash=? WHERE id=?", (digest(token), row["id"]))
    return {"server": svc.server_out(row), "install_command": svc.install_command(token)}


@router.get("/{server_id}", response_model=ServerOut, operation_id="servers_get")
def get_server(server_id: int, _: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)):
    return svc.server_out(_row(db, server_id))


@router.patch("/{server_id}", response_model=ServerOut, operation_id="servers_update")
def patch_server(server_id: int, body: ServerPatch, _: Actor = Depends(require("admin")), db: sqlite3.Connection = Depends(get_db)):
    before = _row(db, server_id)
    changes = body.model_dump(exclude_none=True)
    if "acct_on" in changes:
        changes["acct_on"] = 1 if changes["acct_on"] else 0
    for nullable in ("quota_gb", "quota_reset_day"):  # null clears these; leaving them out keeps them
        if nullable in body.model_fields_set:
            changes[nullable] = getattr(body, nullable)
    if "category_id" in body.model_fields_set:
        changes["category_id"] = _category(db, body.category_id)
    if "role" in changes:
        changes.update(svc.role_columns(changes["role"]))
    changelog.server_patched(db, before, changes)
    for field, value in changes.items():
        db.execute("UPDATE servers SET %s=? WHERE id=?" % field, (value, server_id))  # field names come from the model
    return svc.server_out(_row(db, server_id))


@router.delete("/{server_id}", status_code=204, operation_id="servers_delete")
def delete_server(server_id: int, _: Actor = Depends(require("admin")), db: sqlite3.Connection = Depends(get_db)):
    row = _row(db, server_id)
    changelog.record(db, "server_removed", changelog.label(row), server_id, {"role": row["role"]})
    db.execute("DELETE FROM servers WHERE id=?", (server_id,))


@router.get("/{server_id}/metrics", response_model=MetricsOut, operation_id="servers_metrics")
def metrics(server_id: int, range: str = "24h", _: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)):
    _row(db, server_id)
    span, bucket = svc.RANGES.get(range, svc.RANGES["24h"])
    since = int(time.time()) - span
    rows = db.execute(
        "SELECT (ts/?)*? AS t, AVG(cpu) cpu, AVG(ram_pct) ram, AVG(disk_pct) disk, AVG(rx_bps) rxb, AVG(tx_bps) txb, "
        "SUM(rx_delta) rx, SUM(tx_delta) tx, AVG(steal) steal, AVG(load1) load1, AVG(swap_pct) swap, AVG(retrans) retrans, "
        "AVG(conntrack) conntrack, AVG(conns) conns FROM metrics WHERE server_id=? AND ts>=? GROUP BY t ORDER BY t",
        (bucket, bucket, server_id, since),
    ).fetchall()
    pts = [
        {"ts": r["t"], "cpu": r["cpu"], "ram_pct": r["ram"], "disk_pct": r["disk"], "rx_bps": r["rxb"], "tx_bps": r["txb"], "rx_bytes": r["rx"], "tx_bytes": r["tx"],
         "steal": r["steal"], "load1": r["load1"], "swap_pct": r["swap"], "retrans": r["retrans"], "conntrack": r["conntrack"], "conns": r["conns"]}
        for r in rows
    ]
    return {"range": range, "points": pts, "rx_total": sum(p["rx_bytes"] for p in pts), "tx_total": sum(p["tx_bytes"] for p in pts)}


def _job_out(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"], "kind": r["kind"], "args": json.loads(r["args"]), "status": r["status"],
        "result": json.loads(r["result"]) if r["result"] else None, "error": r["error"],
        "created_at": r["created_at"], "done_at": r["done_at"],
    }


@router.get("/{server_id}/jobs", response_model=List[JobOut], operation_id="servers_jobs")
def list_jobs(server_id: int, _: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)):
    _row(db, server_id)
    return [_job_out(r) for r in db.execute("SELECT * FROM jobs WHERE server_id=? ORDER BY id DESC LIMIT 50", (server_id,))]


@router.post("/{server_id}/jobs", response_model=JobOut, status_code=201, operation_id="servers_create_job")
def create_job(server_id: int, body: JobCreate, actor: Actor = Depends(require("admin")), db: sqlite3.Connection = Depends(get_db)):
    server = _row(db, server_id)
    if body.kind not in svc.SAFE_KINDS | svc.MUTATING_KINDS | svc.DIAG_KINDS | svc.ACTION_KINDS:
        raise DLError("job.kind_unknown")
    if not svc.job_args_valid(body.kind, body.args):
        raise DLError("job.args_invalid")
    if body.kind not in svc.SAFE_KINDS:
        if actor.via == "key" and not actor.full:
            raise DLError("job.permission")  # a read key never changes a server; a full key may
    cur = db.execute(
        "INSERT INTO jobs (server_id, kind, args, created_by, created_at) VALUES (?,?,?,?,?)",
        (server_id, body.kind, json.dumps(body.args), actor.user_id, int(time.time())),
    )
    changelog.job_created(db, server, cur.lastrowid, body.kind, actor.user_id)
    return _job_out(db.execute("SELECT * FROM jobs WHERE id=?", (cur.lastrowid,)).fetchone())
