import sqlite3
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...db import get_db
from ...deps import Actor, require
from ..servers.service import server_out
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
def overview(_: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)):
    servers = [server_out(r) for r in db.execute("SELECT * FROM servers")]
    count = lambda st: sum(1 for s in servers if s["status"] == st)  # noqa: E731
    found, t = svc.issues(db), svc.traffic_24h(db)
    return {
        "servers_total": len(servers), "online": count("online"), "offline": count("offline"), "pending": count("pending"),
        "issues_critical": sum(1 for i in found if i["severity"] == "critical"),
        "issues_warning": sum(1 for i in found if i["severity"] == "warning"),
        "rx_bytes_24h": t["rx_bytes"], "tx_bytes_24h": t["tx_bytes"],
    }


@router.get("/issues", response_model=List[Issue], operation_id="overview_issues")
def issues(_: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)):
    return svc.issues(db)


@router.get("/ping-matrix", response_model=List[PingCell], operation_id="overview_ping_matrix")
def ping_matrix(_: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)):
    return svc.ping_matrix(db)


@router.get("/snapshot", operation_id="overview_snapshot")
def snapshot(_: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)) -> Dict[str, Any]:
    """Everything an AI agent needs in one secret-free JSON document."""
    return {
        "generated_at": int(time.time()),
        "servers": [server_out(r) for r in db.execute("SELECT * FROM servers")],
        "issues": svc.issues(db),
        "ping_matrix": svc.ping_matrix(db),
        "traffic_24h": svc.traffic_24h(db),
    }
