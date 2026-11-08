import sqlite3
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...db import get_db
from ...deps import Actor, current_workspace, require
from ..issues import service as incidents_svc
from ..servers.service import RANGES, server_out
from . import service as svc

router = APIRouter(tags=["overview"])


class Issue(BaseModel):
    id: str
    server_id: Optional[int]
    server_name: Optional[str]
    code: str
    severity: str
    title: str
    suggestion: str
    evidence: Dict[str, Any]
    recent_24h: int = 0


class PingCell(BaseModel):
    from_id: int
    from_name: str
    to_id: Any = None
    to_name: str
    target: str
    loss_pct: Any = None
    rtt_ms: Any = None
    ts: int


class Overview(BaseModel):
    servers_total: int
    online: int
    offline: int
    pending: int
    issues_critical: int
    issues_warning: int
    rx_bytes_24h: int
    tx_bytes_24h: int


@router.get("/overview", response_model=Overview, operation_id="overview_get")
def overview(_: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    servers = [server_out(r) for r in db.execute("SELECT * FROM servers WHERE workspace_id=?", (ws,))]
    count = lambda st: sum(1 for s in servers if s["status"] == st)  # noqa: E731
    found, t = svc.issues(db, ws), svc.traffic_24h(db, ws)
    return {
        "servers_total": len(servers), "online": count("online"), "offline": count("offline"), "pending": count("pending"),
        "issues_critical": sum(1 for i in found if i["severity"] == "critical"),
        "issues_warning": sum(1 for i in found if i["severity"] == "warning"),
        "rx_bytes_24h": t["rx_bytes"], "tx_bytes_24h": t["tx_bytes"],
    }


class FleetPoint(BaseModel):
    ts: int
    rx_bytes: int
    tx_bytes: int
    cpu: Optional[float]
    ram_pct: Optional[float]
    disk_pct: Optional[float]
    servers: int


class FleetHistory(BaseModel):
    range: str
    points: List[FleetPoint]
    rx_total: int
    tx_total: int


@router.get("/overview/history", response_model=FleetHistory, operation_id="overview_history")
def history(range: str = "24h", _: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace),
            db: sqlite3.Connection = Depends(get_db)):
    """The whole fleet over time: traffic summed over every server, usage averaged, how many reported."""
    span, bucket = RANGES.get(range, RANGES["24h"])
    rows = db.execute(
        "SELECT (m.ts/?)*? AS t, SUM(m.rx_delta) rx, SUM(m.tx_delta) tx, AVG(m.cpu) cpu, AVG(m.ram_pct) ram, AVG(m.disk_pct) disk, "
        "COUNT(DISTINCT m.server_id) n FROM metrics m JOIN servers s ON s.id=m.server_id WHERE s.workspace_id=? AND m.ts>=? GROUP BY t ORDER BY t",
        (bucket, bucket, ws, int(time.time()) - span),
    ).fetchall()
    pts = [{"ts": r["t"], "rx_bytes": r["rx"], "tx_bytes": r["tx"], "cpu": r["cpu"], "ram_pct": r["ram"], "disk_pct": r["disk"], "servers": r["n"]} for r in rows]
    return {"range": range, "points": pts, "rx_total": sum(p["rx_bytes"] for p in pts), "tx_total": sum(p["tx_bytes"] for p in pts)}


@router.get("/issues", response_model=List[Issue], operation_id="overview_issues")
def issues(_: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    recent = incidents_svc.recent_counts(db, ws, int(time.time()))
    return [{**i, "recent_24h": recent.get(i["id"], 0)} for i in svc.issues(db, ws)]


@router.get("/ping-matrix", response_model=List[PingCell], operation_id="overview_ping_matrix")
def ping_matrix(_: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    return svc.ping_matrix(db, ws)


@router.get("/snapshot", operation_id="overview_snapshot")
def snapshot(_: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace),
             db: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    """Everything an AI agent needs about the current workspace in one secret-free JSON document."""
    return {
        "generated_at": int(time.time()),
        "servers": [server_out(r) for r in db.execute("SELECT * FROM servers WHERE workspace_id=?", (ws,))],
        "issues": svc.issues(db, ws),
        "ping_matrix": svc.ping_matrix(db, ws),
        "traffic_24h": svc.traffic_24h(db, ws),
    }
