import json
import sqlite3
import time
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from ...db import get_db
from ...deps import Actor, current_workspace, require
from . import briefing as briefing_svc
from . import health as health_svc
from . import periodic, playbooks, render, schemas
from .common import DAY, check_detail, check_format, window

router = APIRouter(prefix="/reports", tags=["reports"])
MAX_EVENTS = 500


def _answer(fmt: str, data: Any, md: Callable[[Any], str]):
    """JSON (typed by the response model) or dense Markdown for an AI assistant."""
    if fmt == "md":
        return PlainTextResponse(md(data), media_type="text/markdown; charset=utf-8")
    return data


@router.get("/briefing", response_model=schemas.Briefing, operation_id="reports_briefing")
def briefing(format: str = "json", detail: str = "brief", _: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace),
             db: sqlite3.Connection = Depends(get_db)):
    """One compact fleet briefing for an AI assistant to read first. format=md is the dense text, detail=full lifts the caps."""
    check_format(format)
    return _answer(format, briefing_svc.build(db, ws, check_detail(detail)), render.briefing_md)


@router.get("/playbooks", response_model=schemas.PlaybookList, operation_id="reports_playbooks")
def list_playbooks(format: str = "json", _: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace)):
    """Every fix guide (code, title, detector live or planned) plus the standing operating rules."""
    check_format(format)
    items = [{k: p[k] for k in ("code", "theme", "title", "summary_fa", "detector")} for p in playbooks.all_playbooks()]
    return _answer(format, {"principles": playbooks.PRINCIPLES, "playbooks": items}, render.playbooks_md)


@router.get("/playbooks/{code}", response_model=schemas.PlaybookOut, operation_id="reports_playbook")
def get_playbook(code: str, format: str = "json", _: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace)):
    """Likely causes, read-only checks, safe fixes and never-do rules for an issue code (ping:<ip> works); unknown codes get the generic guide."""
    check_format(format)
    pb, matched = playbooks.find(code)
    return _answer(format, {"matched": matched, "playbook": pb}, lambda d: render.playbook_md(d["playbook"]))


@router.get("/health", response_model=schemas.HealthOut, operation_id="reports_health")
def health(format: str = "json", _: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace),
           db: sqlite3.Connection = Depends(get_db)):
    """A 0-100 score and band per server, with the penalties and hard gates that fired and the signals not measured yet."""
    check_format(format)
    return _answer(format, health_svc.compute(db, ws), render.health_md)


@router.get("/changes", response_model=schemas.ChangesOut, operation_id="reports_changes")
def changes(since: Optional[int] = None, until: Optional[int] = None, server_id: Optional[int] = None, kind: Optional[str] = None,
            format: str = "json", _: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace),
            db: sqlite3.Connection = Depends(get_db)):
    """The change log of the current workspace, newest first, at most 500 events (default last 24 h)."""
    check_format(format)
    since, until = window(since, until, DAY)
    rows = db.execute(
        "SELECT e.*, COALESCE(NULLIF(s.alias,''), s.name) AS sname FROM events e "
        "LEFT JOIN servers s ON s.id=e.server_id AND s.workspace_id=e.workspace_id WHERE e.workspace_id=? AND e.ts>=? AND e.ts<=? "
        "AND (? IS NULL OR e.server_id=?) AND (? IS NULL OR e.kind=?) ORDER BY e.ts DESC, e.id DESC LIMIT ?",
        (ws, since, until, server_id, server_id, kind or None, kind or None, MAX_EVENTS + 1),
    ).fetchall()
    events = [{"id": r["id"], "ts": r["ts"], "server_id": r["server_id"], "server": r["sname"], "kind": r["kind"], "title": r["title"],
               "detail": json.loads(r["detail"] or "{}")} for r in rows[:MAX_EVENTS]]
    return _answer(format, {"since": since, "until": until, "events": events, "truncated": len(rows) > MAX_EVENTS}, render.changes_md)


def _periodic(fmt: str, since: Optional[int], until: Optional[int], span: int, build: Callable[[int, int], Dict[str, Any]], md: Callable[[Any], str]):
    check_format(fmt)
    s, u = window(since, until, span)
    return _answer(fmt, build(s, u), md)


@router.get("/daily", response_model=schemas.DailyOut, operation_id="reports_daily")
def daily(since: Optional[int] = None, until: Optional[int] = None, format: str = "json", _: Actor = Depends(require("viewer")),
          ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    """The digest: the last 24 h (or since..until) against the equal window before it."""
    counts = lambda: health_svc.compute(db, ws)["counts"]  # noqa: E731
    return _periodic(format, since, until, DAY, lambda s, u: periodic.daily_report(db, ws, s, u, counts()), render.daily_md)


@router.get("/incidents", response_model=schemas.IncidentsReport, operation_id="reports_incidents")
def incidents(since: Optional[int] = None, until: Optional[int] = None, format: str = "json", _: Actor = Depends(require("viewer")),
              ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    """Incident counts by code and server, MTTR, flapping issues and the longest outages (default 7 days)."""
    return _periodic(format, since, until, 7 * DAY, lambda s, u: periodic.incidents_report(db, ws, s, u), render.incidents_md)


@router.get("/traffic", response_model=schemas.TrafficReport, operation_id="reports_traffic")
def traffic(since: Optional[int] = None, until: Optional[int] = None, format: str = "json", _: Actor = Depends(require("viewer")),
              ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    """Fleet and per-server bytes, peak day and hour, relay-exit pair bytes (default 7 days)."""
    return _periodic(format, since, until, 7 * DAY, lambda s, u: periodic.traffic_report(db, ws, s, u), render.traffic_md)


@router.get("/availability", response_model=schemas.AvailabilityReport, operation_id="reports_availability")
def availability(since: Optional[int] = None, until: Optional[int] = None, format: str = "json", _: Actor = Depends(require("viewer")),
              ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    """Per server percent of time reporting, from gaps between reports and offline incidents (default 7 days)."""
    return _periodic(format, since, until, 7 * DAY, lambda s, u: periodic.availability_report(db, ws, s, u), render.availability_md)


@router.get("/capacity", response_model=schemas.CapacityReport, operation_id="reports_capacity")
def capacity(since: Optional[int] = None, until: Optional[int] = None, format: str = "json", _: Actor = Depends(require("viewer")),
              ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    """Peak-hour CPU, steal, load, conntrack and RAM per server, sibling comparison and growth (default 7 days)."""
    return _periodic(format, since, until, 7 * DAY, lambda s, u: periodic.capacity_report(db, ws, s, u), render.capacity_md)


@router.get("/relays", response_model=schemas.RelaysReport, operation_id="reports_relays")
def relays(since: Optional[int] = None, until: Optional[int] = None, format: str = "json", _: Actor = Depends(require("viewer")),
              ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    """Relay-by-exit matrix of loss, RTT and a path verdict, plus bytes per pair (default 7 days for bytes)."""
    return _periodic(format, since, until, 7 * DAY, lambda s, u: periodic.relays_report(db, ws, s, u), render.relays_md)
