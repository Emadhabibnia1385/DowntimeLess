import json
import sqlite3
import time

from fastapi import APIRouter, Depends, Header

from ...db import get_db
from ...errors import DLError
from ...security import digest, new_token
from ...settings import get_settings
from .schemas import EnrollRequest, EnrollResult, Report, ReportResult

router = APIRouter(prefix="/agent/v1", tags=["agent"])


@router.post("/enroll", response_model=EnrollResult, operation_id="agent_enroll")
def enroll(body: EnrollRequest, db: sqlite3.Connection = Depends(get_db)):
    key = new_token(32)
    # the one-time token is burned in the same statement that issues the key
    won = db.execute(
        "UPDATE servers SET agent_hash=?, enroll_hash=NULL, hostname=? WHERE enroll_hash=?",
        (digest(key), body.hostname, digest(body.token)),
    ).rowcount
    if not won:
        raise DLError("agent.enroll_invalid")
    return {"agent_key": key}


@router.post("/report", response_model=ReportResult, operation_id="agent_report")
def report(body: Report, x_agent_key: str = Header(default=""), db: sqlite3.Connection = Depends(get_db)):
    server = db.execute("SELECT * FROM servers WHERE agent_hash=?", (digest(x_agent_key),)).fetchone() if x_agent_key else None
    if not server:
        raise DLError("agent.invalid")
    now, sid = int(time.time()), server["id"]
    net = body.net or {}
    rx, tx = net.get("rx_bytes"), net.get("tx_bytes")
    # monotonic counters: a drop means reboot or reset, so count that sample as zero
    rx_d = rx - server["prev_rx"] if rx is not None and server["prev_rx"] is not None and rx >= server["prev_rx"] else 0
    tx_d = tx - server["prev_tx"] if tx is not None and server["prev_tx"] is not None and tx >= server["prev_tx"] else 0
    geo = body.geo or {}
    public_ip = body.public_ip if body.public_ip and ":" not in body.public_ip else None  # IPv4 only
    pct = lambda used, total: round(used * 100 / total, 1) if total else None  # noqa: E731
    ram_pct = pct((body.ram_total_mb or 0) - (body.ram_avail_mb or 0), body.ram_total_mb)
    disk_pct = pct(body.disk_used_gb or 0, body.disk_total_gb)
    db.execute(
        "UPDATE servers SET last_seen=?, last_report=?, prev_rx=?, prev_tx=?, agent_version=?, hostname=COALESCE(NULLIF(?,''),hostname), "
        "public_ip=COALESCE(?,public_ip), country=COALESCE(?,country), city=COALESCE(?,city), org=COALESCE(?,org) WHERE id=?",
        (now, body.model_dump_json(), rx, tx, body.agent_version, body.hostname, public_ip,
         geo.get("country"), geo.get("city"), geo.get("org"), sid),
    )
    db.execute(
        "INSERT INTO metrics (server_id, ts, cpu, steal, ram_pct, disk_pct, rx_bps, tx_bps, rx_delta, tx_delta, retrans, conntrack) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, now, body.cpu_pct, body.steal_pct, ram_pct, disk_pct, net.get("rx_bps"), net.get("tx_bps"), rx_d, tx_d, body.tcp_retrans_pct, body.conntrack_pct),
    )
    for p in body.ping:
        if "target" in p:
            db.execute("INSERT INTO pings (server_id, ts, target, loss, rtt) VALUES (?,?,?,?,?)", (sid, now, str(p["target"]), p.get("loss_pct"), p.get("rtt_ms")))
    for j in body.jobs_done:
        db.execute(
            "UPDATE jobs SET status=?, result=?, error=?, done_at=? WHERE id=? AND server_id=?",
            (j.status if j.status in ("ok", "error", "rejected") else "error", json.dumps(j.result) if j.result is not None else None, j.error, now, j.id, sid),
        )
    targets = [
        {"target": r["public_ip"], "tcp_port": None}
        for r in db.execute("SELECT public_ip FROM servers WHERE id<>? AND public_ip IS NOT NULL AND public_ip NOT LIKE '%:%'", (sid,))
    ]
    jobs = [{"id": r["id"], "kind": r["kind"], "args": json.loads(r["args"])} for r in db.execute("SELECT * FROM jobs WHERE server_id=? AND status='queued' ORDER BY id", (sid,))]
    if jobs:
        db.execute("UPDATE jobs SET status='sent' WHERE server_id=? AND status='queued'", (sid,))
    return {"interval_s": get_settings().interval_s, "permission": server["permission"], "ping_targets": targets, "jobs": jobs}
