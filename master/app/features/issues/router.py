import sqlite3
import time
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...db import get_db
from ...deps import Actor, current_workspace, require
from ...errors import DLError
from ..overview import service as overview
from . import acks
from . import service as svc

router = APIRouter(tags=["issues"])


class IssueSummary(BaseModel):
    key: str
    code: Optional[str]
    server_id: Optional[int]
    server_name: Optional[str]
    title: Optional[str]
    severity: str
    occurrences: int
    total_s: int
    last_at: int
    active_now: bool
    flapping: bool
    evidence: Dict[str, Any]


class IncidentOut(BaseModel):
    id: int
    key: str
    code: Optional[str]
    server_id: Optional[int]
    server_name: Optional[str]
    severity: str
    title: Optional[str]
    opened_at: int
    closed_at: Optional[int]
    duration_s: int


class HistoryTotals(BaseModel):
    occurrences: int
    issues: int
    active_now: int
    critical: int


class IssuesHistory(BaseModel):
    range: str
    since: int
    summary: List[IssueSummary]
    incidents: List[IncidentOut]
    totals: HistoryTotals


@router.get("/issues/history", response_model=IssuesHistory, operation_id="issues_history")
def history(range: str = "24h", _: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace),
            db: sqlite3.Connection = Depends(get_db)):
    """Every issue that was active during the range, with how often and how long, and each separate occurrence."""
    if range not in svc.RANGES:
        raise DLError("range.invalid")
    return svc.history(db, ws, range, int(time.time()))


class AckIn(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    mode: Literal["until_resolved", "24h", "7d", "always"] = "until_resolved"
    note: str = Field(default="", max_length=acks.MAX_NOTE)


class AckOut(BaseModel):
    key: str
    mode: str
    until: Optional[int]
    note: Optional[str]
    severity: str
    created_at: int


@router.post("/issues/ack", response_model=AckOut, operation_id="issues_ack")
def ack(body: AckIn, actor: Actor = Depends(require("operator")), ws: int = Depends(current_workspace),
        db: sqlite3.Connection = Depends(get_db)):
    """Acknowledge a current issue: it stays listed but is not counted or sent to Telegram until the ack ends."""
    issue = next((i for i in overview.issues(db, ws) if i["id"] == body.key), None)
    if issue is None:
        raise DLError("issue.not_found")
    return acks.add(db, ws, issue, body.mode, body.note, actor.user_id, int(time.time()))


@router.delete("/issues/ack", status_code=204, operation_id="issues_unack")
def unack(key: str, actor: Actor = Depends(require("operator")), ws: int = Depends(current_workspace),
          db: sqlite3.Connection = Depends(get_db)):
    """Undo an acknowledgement: the issue counts and alerts again."""
    if not acks.remove(db, ws, key, actor.user_id, int(time.time())):
        raise DLError("ack.not_found")
