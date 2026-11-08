import re
import sqlite3
import time

from fastapi import APIRouter, Depends

from ...db import get_db
from ...deps import Actor, current_workspace, require
from ...errors import DLError
from ...workspaces import server_row
from ..reports import events as changelog
from ..settings.router import thresholds
from . import memory as m
from . import service as svc
from .schemas import HostHealth, IgnoreOut, IgnoreSet, ListenerDrop, PanelOut

router = APIRouter(tags=["checks"])

NAME_RE = re.compile(r"^[A-Za-z0-9@._:/+=,()\[\] -]{1,128}$")


@router.get("/servers/{server_id}/host-health", response_model=HostHealth, operation_id="checks_host_health")
def host_health(server_id: int, _: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace),
                db: sqlite3.Connection = Depends(get_db)):
    return svc.health_card(db, ws, server_row(db, ws, server_id), thresholds(db, ws), int(time.time()))


@router.patch("/servers/{server_id}/listeners", response_model=HostHealth, operation_id="checks_drop_listener")
def drop_listener(server_id: int, body: ListenerDrop, actor: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
                  db: sqlite3.Connection = Depends(get_db)):
    """A port that was removed on purpose leaves the baseline; if it listens again it is learned again from zero."""
    s = server_row(db, ws, server_id)
    gone = db.execute("DELETE FROM listener_baseline WHERE workspace_id=? AND server_id=? AND proto=? AND port=?",
                      (ws, s["id"], body.proto, body.port)).rowcount
    if not gone:
        raise DLError("listener.not_found")
    changelog.record(db, ws, "check_ack", "%s: %s/%d dropped from the listener baseline" % (s["alias"] or s["name"], body.proto, body.port),
                     s["id"], {"what": "listener", "name": "%s/%d" % (body.proto, body.port), "ignored": True, "user_id": actor.user_id})
    return svc.health_card(db, ws, s, thresholds(db, ws), int(time.time()))


@router.patch("/servers/{server_id}/ignores", response_model=IgnoreOut, operation_id="checks_set_ignore")
def set_ignore(server_id: int, body: IgnoreSet, actor: Actor = Depends(require("admin")), ws: int = Depends(current_workspace),
               db: sqlite3.Connection = Depends(get_db)):
    """Retire a container or a panel node, mark an inbound as group-less on purpose, or accept that DNAT is gone."""
    s = server_row(db, ws, server_id)
    now = int(time.time())
    name = body.name.strip()
    if body.kind == "dnat":
        state = m.load(db, ws, s["id"])
        state.pop("had_dnat", None)
        state["dnat_gone"] = 0
        m.save(db, ws, s["id"], state, now)
        name = "dnat"
    elif not NAME_RE.match(name) or (body.kind == "node" and not name.isdigit()):
        raise DLError("check.invalid")
    elif body.ignored:
        db.execute(
            "INSERT INTO check_ignores (workspace_id, server_id, kind, name, created_by, created_at) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(server_id, kind, name) DO NOTHING",
            (ws, s["id"], body.kind, name, actor.user_id, now),
        )
    else:
        db.execute("DELETE FROM check_ignores WHERE workspace_id=? AND server_id=? AND kind=? AND name=?", (ws, s["id"], body.kind, name))
    changelog.record(db, ws, "check_ack", "%s: %s %s %s" % (s["alias"] or s["name"], body.kind, name, "ignored" if body.ignored else "watched"),
                     s["id"], {"what": body.kind, "name": name, "ignored": body.ignored, "user_id": actor.user_id}, now)
    return {"kind": body.kind, "name": name, "ignored": body.ignored or body.kind == "dnat"}


@router.get("/panel", response_model=PanelOut, operation_id="checks_panel")
def panel_view(_: Actor = Depends(require("viewer")), ws: int = Depends(current_workspace), db: sqlite3.Connection = Depends(get_db)):
    th, now = thresholds(db, ws), int(time.time())
    return {"generated_at": now, "reseller_warn": th["reseller_warn"], "reseller_crit": th["reseller_crit"],
            "node_drop_pct": th["node_drop_pct"],
            "panels": svc.panel_view(db, ws, th, now)}
