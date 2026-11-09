import sqlite3
from typing import Any, Dict, List

from ..overview import service as overview
from ..servers.service import status_of
from ..settings.router import thresholds

PATH_VERDICTS = ("blacklisted", "relay_egress", "relay_filtered")


def _r(v: Any) -> Any:
    return round(v, 1) if v is not None else None


def classify(db: sqlite3.Connection, ws: int) -> List[Dict[str, Any]]:
    """Latest relay-to-exit windows with a verdict taken from the TCP probes (proven ports, 6+ samples).

    exit_down: the exit's agent is silent; blacklisted: TCP fails from every measuring relay (2+); relay_filtered: this
    relay fails TCP to 2+ exits; relay_egress: only this relay fails to this exit; unconfirmed: one relay measures the
    exit by TCP; icmp_only: ICMP loss while TCP is fine or not measured (a note, never a filtering verdict).
    """
    th = thresholds(db, ws)
    windows = overview.path_windows(db, ws)
    servers = db.execute("SELECT * FROM servers WHERE workspace_id=?", (ws,)).fetchall()
    status = {r["id"]: status_of(r) for r in servers}
    names = {r["id"]: r["alias"] or r["name"] for r in servers}
    by_exit: Dict[int, List[Dict[str, Any]]] = {}
    for w in windows:
        w["bad"] = w["tcp_loss"] is not None and w["tcp_loss"] >= th["loss_warn"]
        w["icmp_bad"] = w["loss"] is not None and w["loss"] >= th["loss_warn"]
        by_exit.setdefault(w["to_id"], []).append(w)
    # an exit that fails from every relay says nothing about the relays themselves
    shared = set()
    for e, peers in by_exit.items():
        measured = [p for p in peers if p["tcp_loss"] is not None]
        if len(measured) >= 2 and all(p["bad"] for p in measured):
            shared.add(e)
    bad_per_relay: Dict[int, int] = {}
    for w in windows:
        if w["bad"] and w["to_id"] not in shared:
            bad_per_relay[w["server_id"]] = bad_per_relay.get(w["server_id"], 0) + 1
    out = []
    for w in windows:
        measured = [p for p in by_exit[w["to_id"]] if p["tcp_loss"] is not None]
        if not w["bad"]:
            verdict = "icmp_only" if w["icmp_bad"] else "ok"
        elif status.get(w["to_id"]) == "offline":
            verdict = "exit_down"
        elif len(measured) < 2:
            verdict = "unconfirmed"
        elif w["to_id"] in shared:
            verdict = "blacklisted"
        elif bad_per_relay.get(w["server_id"], 0) >= 2:
            verdict = "relay_filtered"
        else:
            verdict = "relay_egress"
        out.append({
            "relay_id": w["server_id"], "relay": w["from_name"], "exit_id": w["to_id"], "exit": names.get(w["to_id"], "?"),
            "loss_pct": _r(w["loss"]), "rtt_ms": _r(w["rtt"]), "samples": w["n"],
            "tcp_fail_pct": _r(w["tcp_loss"]), "tcp_rtt_ms": _r(w["tcp_rtt"]), "tcp_samples": w["tcp_n"],
            "tls_failed": w["tls_fail"], "verdict": verdict,
        })
    out.sort(key=lambda r: (r["relay"], r["exit"]))
    return out
