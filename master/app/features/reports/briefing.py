import sqlite3
import time
from typing import Any, Dict, List

from ..issues import acks
from ..issues import service as incidents_svc
from ..overview import service as overview
from ..servers.service import current_agent_version, server_out
from ..ssl import service as ssl_svc
from . import health as health_svc
from . import paths, periodic, playbooks
from . import quota as quota_svc
from .common import DAY, day_start, name_of

LIMITS = {
    "brief": {"issues": 15, "recurring": 5, "certs": 5, "pairs": 10, "attention": 6, "changes": 8, "servers": 5},
    "full": {"issues": 60, "recurring": 12, "certs": 15, "pairs": 10, "attention": 40, "changes": 15, "servers": 5},
}
SEV = ("critical", "warning", "info")
# lower runs first; codes not listed go last
PRIORITY = {
    "offline": 0, "quota_exhausted": 1, "quota": 1, "quota_pair": 2, "blacklisted": 1, "relay_filtered": 1, "relay_egress": 1, "conntrack": 2,
    "rebooted": 2, "ip_changed": 2, "listener_missing": 2, "ping": 3, "resized": 3, "disk": 4, "failed_units": 4, "ssl_expiry": 4,
    "ram": 5, "retrans": 5, "ssl_renew_failed": 5, "steal": 6, "cpu": 6, "load_per_core": 6, "ssl_auto_renew_off": 7, "reboot_required": 8, "agent_missing": 9,
}
NOT_MEASURED = [
    "listeners and Xray state on exits", "tunnel units enabled but stopped", "docker/node containers", "DNAT table presence",
    "live conntrack limits vs files", "real-user quality per relay-exit pair (ss -ti)", "panel database, backups, updates, DNS records",
    "reachability from mobile carriers",
]


def _states(servers: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    for s in servers:
        label = s[key] if key == "role" else s["_category"]
        g = groups.setdefault(label, {key if key == "role" else "category": label, "online": 0, "offline": 0, "pending": 0})
        g[s["status"]] += 1
    return sorted(groups.values(), key=lambda g: -(g["online"] + g["offline"] + g["pending"]))


def _group_matrix(bad: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One line per cause: an exit failing from several relays, a relay failing to several exits, or a single pair."""
    out: List[Dict[str, Any]] = []
    for kind, key, other, subject in (("blacklisted", "exit", "relay", "exit"), ("relay_filtered", "relay", "exit", "relay"), ("relay_egress", None, None, None)):
        rows = [p for p in bad if p["verdict"] == kind]
        if key is None:
            out += [{"kind": kind, "server": "%s -> %s" % (p["relay"], p["exit"]), "detail": "loss %s%%" % p["loss_pct"], "source": "matrix"} for p in rows]
            continue
        for name in sorted({p[key] for p in rows}):
            mine = [p for p in rows if p[key] == name]
            out.append({"kind": kind, "server": name, "source": "matrix",
                        "detail": "%s %s: loss %s%% avg" % ("fails from" if key == "exit" else "fails to", ",".join(sorted(p[other] for p in mine)),
                                                           round(sum(p["loss_pct"] or 0 for p in mine) / len(mine)))})
    return out


def _check_first(issues: List[Dict[str, Any]], outdated: List[str], pair_problems: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    for i in issues:
        code = playbooks.normalise(i["code"])
        g = groups.setdefault(code, {"code": code, "severity": i["severity"], "servers": [], "count": 0, "title": i["title"]})
        g["count"] += 1
        if i["server_name"] and i["server_name"] not in g["servers"]:
            g["servers"].append(i["server_name"])
        if SEV.index(i["severity"]) < SEV.index(g["severity"]):
            g["severity"] = i["severity"]
    ordered = sorted(groups.values(), key=lambda g: (SEV.index(g["severity"]), PRIORITY.get(g["code"], 20), -g["count"], g["code"]))
    steps = [{
        "code": g["code"], "severity": g["severity"], "count": g["count"], "servers": g["servers"][:4],
        "first_check": playbooks.first_check(g["code"]), "playbook": "/api/v1/reports/playbooks/%s" % g["code"],
        "why": g["title"],
    } for g in ordered[:5]]
    if len(steps) < 5 and pair_problems and not any(s["code"] in paths.PATH_VERDICTS for s in steps):
        p = pair_problems[0]
        steps.append({"code": p["kind"], "severity": "warning", "count": len(pair_problems), "servers": [p["server"]],
                      "first_check": playbooks.first_check(p["kind"]), "playbook": "/api/v1/reports/playbooks/%s" % p["kind"], "why": p["detail"]})
    if len(steps) < 5 and outdated:
        steps.append({"code": "agent_outdated", "severity": "info", "count": len(outdated), "servers": outdated[:4], "first_check": None,
                      "playbook": None, "why": "agent older than the one this panel serves; update with the self_update job"})
    return steps


def build(db: sqlite3.Connection, ws: int, detail: str = "brief", now: int = 0) -> Dict[str, Any]:
    now = now or int(time.time())
    lim = LIMITS[detail]
    raw_servers = db.execute("SELECT * FROM servers WHERE workspace_id=?", (ws,)).fetchall()
    rows = [dict(server_out(r), _category=None) for r in raw_servers]
    cats = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM categories WHERE workspace_id=?", (ws,))}
    for r, raw in zip(rows, raw_servers):
        r["_category"] = cats.get(raw["category_id"], "-")
    every = overview.issues(db, ws)
    found = acks.loud(every)  # acknowledged issues are listed apart, never counted or checked first
    recent = incidents_svc.recent_counts(db, ws, now)
    sev_counts = {s: sum(1 for i in found if i["severity"] == s) for s in SEV}
    issue_items = [{
        "severity": i["severity"], "server_id": i["server_id"], "server": i["server_name"], "code": i["code"], "title": i["title"],
        "evidence": i["evidence"], "suggestion": i["suggestion"], "recent_24h": recent.get(i["id"], 0),
    } for i in found]
    hist = incidents_svc.history(db, ws, "24h", now)
    recurring = [{"server": s["server_name"], "code": s["code"], "occurrences": s["occurrences"], "total_s": s["total_s"],
                  "active_now": s["active_now"], "flapping": s["flapping"]} for s in hist["summary"] if s["occurrences"] >= 2]
    matrix = paths.classify(db, ws)
    from_issues = [{"kind": i["code"], "server": i["server_name"], "detail": i["title"], "source": "issue"} for i in found if i["code"] in paths.PATH_VERDICTS]
    from_matrix = _group_matrix([p for p in matrix if p["verdict"] in paths.PATH_VERDICTS])
    problems = from_issues or from_matrix
    hs = health_svc.compute(db, ws, every, now)
    attention = [{
        "server_id": h["server_id"], "name": h["name"], "role": h["role"], "score": h["score"], "band": h["band"],
        "gates": [g["key"] for g in h["gates"]], "top_penalty": h["penalties"][0]["detail"] if h["penalties"] else None,
    } for h in hs["servers"] if h["band"] in ("failing", "degraded")]
    today = day_start(now)
    t = {
        "today": periodic.fleet_bytes(db, ws, today, now), "yesterday": periodic.fleet_bytes(db, ws, today - DAY, today),
        "last_7d": periodic.fleet_bytes(db, ws, now - 7 * DAY, now),
    }
    pairs = periodic.link_pairs(db, ws, now - 7 * DAY, now, lim["pairs"])
    certs = [{
        "name": c["name"], "server": c["server_name"], "days_left": c["days_left"], "level": c["level"], "auto_renew": c["auto_renew"], "error": c["error"],
    } for c in ssl_svc.rows(db, ws) if not c["stale"] and (c["level"] != "ok" or (c["kind"] == "file" and c["auto_renew"] == "off" and c["days_left"] is not None and c["days_left"] <= 45))]
    outdated = [r["name"] if not r["alias"] else r["alias"] for r in rows if r["agent_outdated"]]
    quota = quota_svc.forecast(db, ws, now)
    changes = db.execute(
        "SELECT ts, server_id, kind, title FROM events WHERE workspace_id=? AND ts>=? AND kind NOT IN ('issue_opened','issue_closed') "
        "ORDER BY ts DESC, id DESC LIMIT ?",
        (ws, now - DAY, lim["changes"] + 1)).fetchall()
    names = {r["id"]: name_of(r) for r in raw_servers}
    counted = db.execute(
        "SELECT COUNT(*) c FROM events WHERE workspace_id=? AND ts>=? AND kind IN ('issue_opened','issue_closed')", (ws, now - DAY)
    ).fetchone()["c"]
    check = _check_first(found, outdated, from_matrix if not from_issues else [])
    return {
        "generated_at": now, "detail": detail, "timezone_note": "today/yesterday are Tehran days (UTC+3:30); other times are UTC",
        "fleet": {
            "total": len(rows), "online": sum(1 for r in rows if r["status"] == "online"), "offline": sum(1 for r in rows if r["status"] == "offline"),
            "pending": sum(1 for r in rows if r["status"] == "pending"), "by_role": _states(rows, "role"), "by_category": _states(rows, "category"),
        },
        "issues": {**sev_counts, "items": issue_items[: lim["issues"]], "truncated": len(issue_items) > lim["issues"]},
        "recurring_24h": recurring[: lim["recurring"]],
        "path_problems": problems,
        "health": {"counts": hs["counts"], "attention": attention[: lim["attention"]], "truncated": len(attention) > lim["attention"]},
        "traffic": {**t, "top_servers": periodic.server_bytes(db, ws, now - 7 * DAY, now, lim["servers"]), "pairs_7d": pairs,
                    "link_counting": any(r["acct_on"] for r in raw_servers)},
        "quota": quota,
        "certs_at_risk": certs[: lim["certs"]],
        "agents_outdated": {"latest": current_agent_version(), "servers": outdated},
        "changes_24h": [{"ts": r["ts"], "server": names.get(r["server_id"]), "kind": r["kind"], "title": r["title"]} for r in changes[: lim["changes"]]],
        "issue_events_24h": counted,
        "check_first": check,
        "acknowledged": acks.brief(every)[: lim["issues"]],
        "not_measured": NOT_MEASURED + (["quota (no quota set on any server)"] if not quota else []),
    }
