import json
import logging
import sqlite3
import time

from fastapi import APIRouter, Depends, Header

from ...db import get_db
from ...errors import DLError
from ...security import digest, new_token
from ...settings import get_settings
from ..checks import memory as checks_memory
from ..servers import events
from ..servers.service import swap_pct
from ..links import service as links_svc
from ..overview import probes as probes_svc
from ..reports import events as changelog
from ..ssl.service import adopt_domains
from .schemas import EnrollRequest, EnrollResult, Report, ReportResult

router = APIRouter(prefix="/agent/v1", tags=["agent"])
log = logging.getLogger("dl.agent")


@router.post("/enroll", response_model=EnrollResult, operation_id="agent_enroll")
def enroll(body: EnrollRequest, db: sqlite3.Connection = Depends(get_db)):
    key = new_token(32)
    # the one-time token is burned in the same statement that issues the key
    won = db.execute(  # ws: token_lookup - the one-time token names exactly one server
        "UPDATE servers SET agent_hash=?, enroll_hash=NULL, hostname=? WHERE enroll_hash=?",
        (digest(key), body.hostname, digest(body.token)),
    ).rowcount
    if not won:
        raise DLError("agent.enroll_invalid")
    return {"agent_key": key}


@router.post("/report", response_model=ReportResult, operation_id="agent_report")
def report(body: Report, x_agent_key: str = Header(default=""), db: sqlite3.Connection = Depends(get_db)):
    server = db.execute(  # ws: token_lookup - the agent key names exactly one server
        "SELECT * FROM servers WHERE agent_hash=?", (digest(x_agent_key),)
    ).fetchone() if x_agent_key else None
    if not server:
        raise DLError("agent.invalid")
    now, sid, ws = int(time.time()), server["id"], server["workspace_id"]
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
    changes = events.detect(server, body, public_ip, now)
    for column, value in changes.items():
        db.execute("UPDATE servers SET %s=? WHERE id=? AND workspace_id=?" % column, (value, sid, ws))  # column names come from detect()
    changelog.report_changes(db, server, body, now, changes)
    db.execute(
        "UPDATE servers SET last_seen=?, last_report=?, prev_rx=?, prev_tx=?, agent_version=?, hostname=COALESCE(NULLIF(?,''),hostname), "
        "public_ip=COALESCE(?,public_ip), country=COALESCE(?,country), city=COALESCE(?,city), org=COALESCE(?,org) WHERE id=? AND workspace_id=?",
        (now, body.model_dump_json(), rx, tx, body.agent_version, body.hostname, public_ip,
         geo.get("country"), geo.get("city"), geo.get("org"), sid, ws),
    )
    dumped = body.model_dump()
    try:
        checks_memory.observe(db, server, dumped, now)
    except Exception:  # a bad field in the new blocks must never cost the whole report
        log.exception("check memory of server %d failed", sid)
    extra = body.model_extra or {}
    db.execute(  # ws: agent_server
        "INSERT INTO metrics (server_id, ts, cpu, steal, ram_pct, disk_pct, rx_bps, tx_bps, rx_delta, tx_delta, retrans, conntrack, load1, swap_pct, conns) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, now, body.cpu_pct, body.steal_pct, ram_pct, disk_pct, net.get("rx_bps"), net.get("tx_bps"), rx_d, tx_d, body.tcp_retrans_pct, body.conntrack_pct,
         extra.get("load1"), swap_pct(extra), extra.get("tcp_established")),
    )
    links_svc.record(db, sid, extra.get("acct"), now)
    found = ((body.model_extra or {}).get("ssl") or {}).get("domains")
    if isinstance(found, list):
        adopt_domains(db, server, found)
    for p in body.ping:
        if "target" in p:
            db.execute(  # ws: agent_server - readers join targets inside the same workspace
                "INSERT INTO pings (server_id, ts, target, loss, rtt) VALUES (?,?,?,?,?)", (sid, now, str(p["target"]), p.get("loss_pct"), p.get("rtt_ms"))
            )
    try:
        probes_svc.record(db, server, extra.get("probes"), now, dumped)
    except Exception:  # a malformed probe list must never cost the whole report
        log.exception("probes of server %d failed", sid)
    for j in body.jobs_done:
        changelog.job_done(db, server, j.id, j.status)
        db.execute(  # ws: agent_server - only its own jobs
            "UPDATE jobs SET status=?, result=?, error=?, done_at=? WHERE id=? AND server_id=?",
            (j.status if j.status in ("ok", "error", "rejected") else "error", json.dumps(j.result) if j.result is not None else None, j.error, now, j.id, sid),
        )
    # only Iran relays measure, and only towards foreign servers: foreign-to-foreign pings are noise
    # and only towards servers of their own workspace
    targets = [
        {"target": r["public_ip"], "tcp_port": None}
        for r in db.execute(
            "SELECT public_ip FROM servers WHERE workspace_id=? AND role<>'relay' AND public_ip IS NOT NULL AND public_ip NOT LIKE '%:%'",
            (ws,),
        )
    ] if server["role"] == "relay" else []
    jobs = [{"id": r["id"], "kind": r["kind"], "args": json.loads(r["args"])} for r in db.execute(
        "SELECT * FROM jobs WHERE server_id=? AND status='queued' ORDER BY id", (sid,))]  # ws: agent_server - its own jobs
    if jobs:
        db.execute("UPDATE jobs SET status='sent' WHERE server_id=? AND status='queued'", (sid,))  # ws: agent_server - its own jobs
    probe_targets = probes_svc.targets_for_relay(db, ws, now, sid) if server["role"] == "relay" else []
    return {"interval_s": get_settings().interval_s, "permission": "full", "ping_targets": targets, "probe_targets": probe_targets, "jobs": jobs,
            "acct_peers": links_svc.peers_for(db, server), "peers": links_svc.workspace_peers(db, server)}
