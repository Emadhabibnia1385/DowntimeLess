import sqlite3
import time
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...db import get_db
from ...deps import Actor, require
from ...errors import DLError

router = APIRouter(prefix="/links", tags=["links"])
MAX_WINDOW_S = 366 * 86400


class LinkRow(BaseModel):
    server_id: int
    server_name: str
    server_role: str
    peer_ip: str
    peer_id: Optional[int]
    peer_name: Optional[str]
    peer_role: Optional[str]
    in_bytes: int
    out_bytes: int


class LinksOut(BaseModel):
    since: int
    until: int
    links: List[LinkRow]


class LinkPoint(BaseModel):
    ts: int
    in_bytes: int
    out_bytes: int


class LinkSeries(BaseModel):
    server_id: int
    peer_ip: str
    since: int
    until: int
    points: List[LinkPoint]


def _window(since: Optional[int], until: Optional[int]):
    now = int(time.time())
    until = until if until is not None else now
    since = since if since is not None else until - 7 * 86400
    if since < 0 or until <= since or until - since > MAX_WINDOW_S:
        raise DLError("window.invalid")
    return since, until


@router.get("/traffic", response_model=LinksOut, operation_id="links_traffic")
def traffic(since: Optional[int] = None, until: Optional[int] = None, category: Optional[str] = None, _: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)):
    """Bytes each server exchanged with each peer server in a window (hour resolution), biggest first.

    With `category` (an id or 'none') only links where the server or its peer is in that category.
    """
    since, until = _window(since, until)
    if category in (None, ""):
        cat_sql, cat_args = "1=1", []
    elif category == "none":
        cat_sql, cat_args = "(s.category_id IS NULL OR p.category_id IS NULL)", []
    elif category.isdigit():
        cat_sql, cat_args = "(s.category_id=? OR p.category_id=?)", [int(category), int(category)]
    else:
        raise DLError("traffic.category_invalid")
    rows = db.execute(
        "SELECT l.server_id, COALESCE(NULLIF(s.alias,''), s.name) AS server_name, s.role AS server_role, l.peer_ip, "
        "p.id AS peer_id, COALESCE(NULLIF(p.alias,''), p.name) AS peer_name, p.role AS peer_role, "
        "SUM(l.in_bytes) AS in_bytes, SUM(l.out_bytes) AS out_bytes "
        "FROM link_traffic l JOIN servers s ON s.id=l.server_id LEFT JOIN servers p ON p.public_ip=l.peer_ip "
        "WHERE l.hour>=? AND l.hour<? AND %s GROUP BY l.server_id, l.peer_ip ORDER BY SUM(l.in_bytes)+SUM(l.out_bytes) DESC" % cat_sql,
        [since - since % 3600, until] + cat_args,
    ).fetchall()
    return {"since": since, "until": until, "links": [dict(r) for r in rows]}


@router.get("/traffic/series", response_model=LinkSeries, operation_id="links_series")
def series(server_id: int, peer_ip: str, since: Optional[int] = None, until: Optional[int] = None,
           _: Actor = Depends(require("viewer")), db: sqlite3.Connection = Depends(get_db)):
    since, until = _window(since, until)
    rows = db.execute(
        "SELECT hour AS ts, in_bytes, out_bytes FROM link_traffic WHERE server_id=? AND peer_ip=? AND hour>=? AND hour<? ORDER BY hour",
        (server_id, peer_ip, since - since % 3600, until),
    ).fetchall()
    return {"server_id": server_id, "peer_ip": peer_ip, "since": since, "until": until, "points": [dict(r) for r in rows]}
