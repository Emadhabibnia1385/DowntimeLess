import sqlite3
from typing import Any, Dict, List

from ..overview import service as overview
from ..servers.service import status_of
from ..settings.router import thresholds

PATH_VERDICTS = ("blacklisted", "relay_egress", "relay_filtered")


def classify(db: sqlite3.Connection, ws: int) -> List[Dict[str, Any]]:
    """Latest relay-to-exit pings with a verdict. ICMP only: a verdict is a hypothesis to confirm with a data test.

    exit_down: the exit's agent is silent; blacklisted: every measuring relay (2+) fails; relay_filtered: this relay
    fails to 2+ exits; relay_egress: only this relay fails to this exit; unconfirmed: a single relay measures the exit.
    """
    th = thresholds(db, ws)
    windows = overview.ping_windows(db, ws)
    servers = db.execute("SELECT * FROM servers WHERE workspace_id=?", (ws,)).fetchall()
    status = {r["id"]: status_of(r) for r in servers}
    names = {r["id"]: r["alias"] or r["name"] for r in servers}
    by_exit: Dict[int, List[Dict[str, Any]]] = {}
    for w in windows:
        w["bad"] = w["loss"] is not None and w["loss"] >= th["loss_warn"]
        by_exit.setdefault(w["to_id"], []).append(w)
    # an exit that fails from every relay says nothing about the relays themselves
    shared = {e for e, peers in by_exit.items() if len(peers) >= 2 and all(p["bad"] for p in peers)}
    bad_per_relay: Dict[int, int] = {}
    for w in windows:
        if w["bad"] and w["to_id"] not in shared:
            bad_per_relay[w["server_id"]] = bad_per_relay.get(w["server_id"], 0) + 1
    out = []
    for w in windows:
        peers = by_exit[w["to_id"]]
        if not w["bad"]:
            verdict = "ok"
        elif status.get(w["to_id"]) == "offline":
            verdict = "exit_down"
        elif len(peers) < 2:
            verdict = "unconfirmed"
        elif w["to_id"] in shared:
            verdict = "blacklisted"
        elif bad_per_relay.get(w["server_id"], 0) >= 2:
            verdict = "relay_filtered"
        else:
            verdict = "relay_egress"
        out.append({
            "relay_id": w["server_id"], "relay": w["from_name"], "exit_id": w["to_id"], "exit": names.get(w["to_id"], "?"),
            "loss_pct": round(w["loss"], 1) if w["loss"] is not None else None,
            "rtt_ms": round(w["rtt"], 1) if w["rtt"] is not None else None, "samples": w["n"], "verdict": verdict,
        })
    out.sort(key=lambda r: (r["relay"], r["exit"]))
    return out
