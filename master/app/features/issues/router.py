import sqlite3
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...db import get_db
from ...deps import Actor, require
from ...errors import DLError
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
def history(range: str = "24h", _: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)):
    """Every issue that was active during the range, with how often and how long, and each separate occurrence."""
    if range not in svc.RANGES:
        raise DLError("range.invalid")
    return svc.history(db, range, int(time.time()))
