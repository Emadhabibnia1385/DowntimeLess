"""The doors other features use: issues per server, the server's host-health card and the PasarGuard panel view."""
import sqlite3
from typing import Any, Dict, Iterable, List, Optional

from . import drift, host, memory as m, panel, quality

PANEL_LIMIT = 10  # panel hosts shown per workspace


def context(servers: Iterable[sqlite3.Row]) -> Dict[str, Any]:
    """What a rule may look up on another server of the same workspace: a node's host by its public IP."""
    by_ip: Dict[str, Dict[str, Any]] = {}
    rows: Dict[str, Any] = {}
    for s in servers:
        if s["public_ip"]:
            rows.setdefault(s["public_ip"], s)
        if s["public_ip"] and s["last_report"]:
            by_ip.setdefault(s["public_ip"], m.report_of(s))
    return {"by_ip": by_ip, "servers_by_ip": rows}


def has_data(rep: Dict[str, Any]) -> bool:
    return m.checks_of(rep) is not None or m.panel_of(rep) is not None or isinstance(rep.get("panel_error"), str)


def server_issues(db: sqlite3.Connection, ws: int, s, th: Dict[str, float], now: int, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    rep = m.report_of(s)
    if not has_data(rep):
        return []
    state, ignored = m.load(db, ws, s["id"]), m.ignored(db, ws, s["id"])
    rows = m.baseline(db, ws, s["id"]) if m.checks_of(rep) is not None else []
    return (host.issues(s, th, rep, state, rows, ignored, now) + drift.issues(s, th, rep, state, now)
            + quality.issues(s, th, rep, state, ctx, now) + panel.issues(db, ws, s, th, rep, state, ignored, ctx, now))


def _pct(count: Optional[int], limit: Optional[int]) -> Optional[float]:
    return round(count * 100.0 / limit, 1) if count is not None and limit else None


def health_card(db: sqlite3.Connection, ws: int, s, th: Dict[str, float], now: int) -> Dict[str, Any]:
    """The server's `checks` in one compact shape for the «سلامت میزبان» card."""
    rep = m.report_of(s)
    checks = m.checks_of(rep)
    errors = [e for e in rep.get("checks_error") or [] if isinstance(e, str)][:20]
    card: Dict[str, Any] = {"server_id": s["id"], "has_checks": checks is not None, "agent_version": rep.get("agent_version") or None,
                            "checks_error": errors, "listeners": None, "units": None, "containers": None, "nft": None,
                            "conntrack": None, "kernel": None, "apt": None, "security": None}
    if checks is None:
        return card
    state, ignored = m.load(db, ws, s["id"]), m.ignored(db, ws, s["id"])
    rows = m.baseline(db, ws, s["id"])
    lp = host.listener_problems(s, rep, state, rows)
    if lp is not None:
        missing = [r for r in rows if m.in_baseline(r) and r["missing"] > 0]
        card["listeners"] = {
            "current": lp["current"], "baseline": lp["baseline"], "learning": lp["learning"],
            "missing": [{"proto": r["proto"], "port": r["port"], "proc": r["proc"], "missing_reports": r["missing"],
                         "alerting": r["missing"] >= lp["need"]} for r in missing],
        }
    units = m.dicts(checks.get("units"))
    if units is not None:
        memo = state.get("units") if isinstance(state.get("units"), dict) else {}
        card["units"] = [{
            "name": u["name"], "enabled": u.get("enabled") is True, "active": m.text(u.get("active"), 20), "sub": m.text(u.get("sub"), 20),
            "restarts": m.num(u.get("restarts")), "restarts_10m": m.num((memo.get(u["name"]) or {}).get("rise")) or 0,
            "tunnel": bool(m.UNIT_FAMILY.match(u["name"])),
        } for u in units if isinstance(u.get("name"), str)][:100]
    containers = m.dicts(checks.get("containers"))
    if containers is not None:
        card["containers"] = [{
            "name": c["name"], "image": m.text(c.get("image"), 100), "state": m.text(c.get("state"), 20),
            "health": m.text(c.get("health"), 20), "restarts": m.num(c.get("restarts")), "policy": m.text(c.get("policy"), 20),
            "retired": c["name"] in ignored.get("container", set()),
        } for c in containers if isinstance(c.get("name"), str)][:50]
    nft = checks.get("nft")
    if isinstance(nft, dict):
        had = state.get("had_dnat") if isinstance(state.get("had_dnat"), dict) else None
        card["nft"] = {"relay_dnat": nft.get("relay_dnat") is True, "dnat_rules": m.num(nft.get("dnat_rules")),
                       "tables": len(nft.get("tables") or []) if isinstance(nft.get("tables"), list) else None,
                       "ip_forward": m.num(nft.get("ip_forward")), "had_dnat": bool(had)}
    ct = checks.get("conntrack")
    if isinstance(ct, dict):
        card["conntrack"] = {"module_loaded": ct.get("module_loaded") is True, "count": m.num(ct.get("count")), "max": m.num(ct.get("max")),
                             "pct": _pct(m.num(ct.get("count")), m.num(ct.get("max"))),
                             "tcp_established_timeout": m.num(ct.get("tcp_established_timeout")),
                             "insert_failed": m.num(ct.get("insert_failed")), "drop": m.num(ct.get("drop")), "early_drop": m.num(ct.get("early_drop"))}
    kernel = checks.get("kernel")
    if isinstance(kernel, dict):
        num_or_float = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) else None  # noqa: E731
        card["kernel"] = {"congestion": m.text(kernel.get("congestion"), 20), "qdisc": m.text(kernel.get("qdisc"), 20),
                          "ip_forward": m.num(kernel.get("ip_forward")), "oom_kill": m.num(kernel.get("oom_kill")),
                          "ntp_synced": kernel.get("ntp_synced") if isinstance(kernel.get("ntp_synced"), bool) else None,
                          "inode_pct": num_or_float(kernel.get("inode_pct")), "journal_mb": num_or_float(kernel.get("journal_mb")),
                          "mtu_probing": m.num(kernel.get("mtu_probing")), "swappiness": m.num(kernel.get("swappiness"))}
    apt = checks.get("apt")
    if isinstance(apt, dict):
        card["apt"] = {"dpkg_audit": m.num(apt.get("dpkg_audit")), "reboot_required_pkgs": m.num(apt.get("reboot_required_pkgs")),
                       "held_docker": apt.get("held_docker") if isinstance(apt.get("held_docker"), bool) else None}
    sec = checks.get("security")
    if isinstance(sec, dict):
        ports = sec.get("sshd_ports")
        card["security"] = {"ufw": m.text(sec.get("ufw"), 20), "fail2ban": m.text(sec.get("fail2ban"), 20),
                            "password_auth": sec.get("password_auth") if isinstance(sec.get("password_auth"), bool) else None,
                            "sshd_ports": [p for p in ports if m.num(p) is not None][:10] if isinstance(ports, list) else None}
    return card


def panel_view(db: sqlite3.Connection, ws: int, th: Dict[str, float], now: int) -> List[Dict[str, Any]]:
    """Every panel host of the workspace that reports `panel` (or a panel read error), with its tables."""
    servers = db.execute("SELECT * FROM servers WHERE workspace_id=? AND last_report IS NOT NULL ORDER BY name", (ws,)).fetchall()
    ctx = context(servers)
    out = []
    for s in servers:
        rep = m.report_of(s)
        if m.panel_of(rep) is None and not isinstance(rep.get("panel_error"), str):
            continue
        out.append(panel.view(db, ws, s, th, rep, m.load(db, ws, s["id"]), m.ignored(db, ws, s["id"]), ctx, now))
        if len(out) >= PANEL_LIMIT:
            break
    return out
