import json
import re
import sqlite3
import time
from typing import List

from fastapi import APIRouter, Depends

from ...db import get_db
from ...deps import ROLE_RANK, Actor, current_workspace, require
from ...errors import DLError
from ...security import digest, new_token
from ...workspaces import MAX_SERVERS, server_row
from ..reports import events as changelog
from . import service as svc
from .schemas import JobCreate, JobOut, MetricsOut, ServerCreate, ServerCreated, ServerOut, ServerPatch

router = APIRouter(prefix="/servers", tags=["servers"])


def _category(db: sqlite3.Connection, ws: int, category_id):
    if category_id is not None and not db.execute("SELECT 1 FROM categories WHERE id=? AND workspace_id=?", (category_id, ws)).fetchone():
        raise DLError("category.not_found")
    return category_id


@router.get("", response_model=List[ServerOut], operation_id="servers_list")
def list_servers(_: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    return [svc.server_out(r) for r in db.execute("SELECT * FROM servers WHERE workspace_id=? ORDER BY role, name", (ws,))]


@router.post("", response_model=ServerCreated, status_code=201, operation_id="servers_create")
def create_server(body: ServerCreate, _: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
                  db: sqlite3.Connection = Depends(get_db)):
    if db.execute("SELECT COUNT(*) FROM servers WHERE workspace_id=?", (ws,)).fetchone()[0] >= MAX_SERVERS:
        raise DLError("server.limit")
    token = new_token(24)
    cols = svc.role_columns(body.role)
    cur = db.execute(
        "INSERT INTO servers (workspace_id, name, alias, role, panel_only, category_id, enroll_hash, created_at, permission, acct_on) "
        "VALUES (?,?,?,?,?,?,?,?,'full',1)",
        (ws, body.name, body.alias, cols["role"], cols["panel_only"], _category(db, ws, body.category_id), digest(token), int(time.time())),
    )
    changelog.record(db, ws, "server_added", "%s (%s)" % (body.name, body.role), cur.lastrowid, {"role": body.role})
    return {"server": svc.server_out(server_row(db, ws, cur.lastrowid)), "install_command": svc.install_command(token)}


@router.post("/{server_id}/enroll-token", response_model=ServerCreated, operation_id="servers_new_enroll_token")
def new_enroll_token(server_id: int, _: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
                     db: sqlite3.Connection = Depends(get_db)):
    row = server_row(db, ws, server_id)
    token = new_token(24)
    db.execute("UPDATE servers SET enroll_hash=? WHERE id=? AND workspace_id=?", (digest(token), row["id"], ws))
    return {"server": svc.server_out(row), "install_command": svc.install_command(token)}


@router.get("/{server_id}", response_model=ServerOut, operation_id="servers_get")
def get_server(server_id: int, _: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace),
               db: sqlite3.Connection = Depends(get_db)):
    return svc.server_out(server_row(db, ws, server_id))


@router.patch("/{server_id}", response_model=ServerOut, operation_id="servers_update")
def patch_server(server_id: int, body: ServerPatch, _: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
                 db: sqlite3.Connection = Depends(get_db)):
    before = server_row(db, ws, server_id)
    changes = body.model_dump(exclude_none=True)
    for flag in ("acct_on", "count_upload"):
        if flag in changes:
            changes[flag] = 1 if changes[flag] else 0
    for nullable in ("quota_gb", "quota_reset_day"):  # null clears these; leaving them out keeps them
        if nullable in body.model_fields_set:
            changes[nullable] = getattr(body, nullable)
    if "category_id" in body.model_fields_set:
        changes["category_id"] = _category(db, ws, body.category_id)
    if "role" in changes:
        changes.update(svc.role_columns(changes["role"]))
    changelog.server_patched(db, before, changes)
    for field, value in changes.items():
        # field names come from the model
        db.execute("UPDATE servers SET %s=? WHERE id=? AND workspace_id=?" % field, (value, server_id, ws))
    return svc.server_out(server_row(db, ws, server_id))


@router.delete("/{server_id}", status_code=204, operation_id="servers_delete")
def delete_server(server_id: int, _: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
                  db: sqlite3.Connection = Depends(get_db)):
    row = server_row(db, ws, server_id)
    changelog.record(db, ws, "server_removed", changelog.label(row), server_id, {"role": row["role"]})
    db.execute("DELETE FROM servers WHERE id=? AND workspace_id=?", (server_id, ws))


@router.get("/{server_id}/metrics", response_model=MetricsOut, operation_id="servers_metrics")
def metrics(server_id: int, range: str = "24h", _: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace),
            db: sqlite3.Connection = Depends(get_db)):
    server_row(db, ws, server_id)
    span, bucket = svc.RANGES.get(range, svc.RANGES["24h"])
    since = int(time.time()) - span
    rows = db.execute(
        "SELECT (ts/?)*? AS t, AVG(cpu) cpu, AVG(ram_pct) ram, AVG(disk_pct) disk, AVG(rx_bps) rxb, AVG(tx_bps) txb, "
        "SUM(rx_delta) rx, SUM(tx_delta) tx, AVG(steal) steal, AVG(load1) load1, AVG(swap_pct) swap, AVG(retrans) retrans, "
        "AVG(conntrack) conntrack, AVG(conns) conns FROM metrics WHERE server_id=? AND ts>=? GROUP BY t ORDER BY t",  # ws: server_row - checked above
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
def list_jobs(server_id: int, _: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace),
              db: sqlite3.Connection = Depends(get_db)):
    server_row(db, ws, server_id)
    return [_job_out(r) for r in db.execute("SELECT * FROM jobs WHERE server_id=? ORDER BY id DESC LIMIT 50", (server_id,))]  # ws: server_row - checked above


@router.post("/{server_id}/jobs", response_model=JobOut, status_code=201, operation_id="servers_create_job")
def create_job(server_id: int, body: JobCreate, actor: Actor = Depends(require("operator")), ws: int = Depends(current_workspace),
               db: sqlite3.Connection = Depends(get_db)):
    server = server_row(db, ws, server_id)
    if body.kind not in svc.SAFE_KINDS | svc.MUTATING_KINDS | svc.DIAG_KINDS | svc.ACTION_KINDS:
        raise DLError("job.kind_unknown")
    # an operator runs checks only; anything that changes the server needs an admin
    if body.kind not in svc.OPERATOR_KINDS and ROLE_RANK[actor.role] < ROLE_RANK["admin"]:
        raise DLError("auth.forbidden")
    if not svc.job_args_valid(body.kind, body.args):
        raise DLError("job.args_invalid")
    if body.kind not in svc.SAFE_KINDS:
        if actor.via == "key" and not actor.full:
            raise DLError("job.permission")  # a read key never changes a server; a full key may
    cur = db.execute(
        "INSERT INTO jobs (server_id, kind, args, created_by, created_at) VALUES (?,?,?,?,?)",  # ws: server_row - checked above
        (server_id, body.kind, json.dumps(body.args), actor.user_id, int(time.time())),
    )
    changelog.job_created(db, server, cur.lastrowid, body.kind, actor.user_id)
    return _job_out(db.execute("SELECT * FROM jobs WHERE id=?", (cur.lastrowid,)).fetchone())  # ws: server_row - the job just inserted for it
