"""Real-user path quality and tunnel health (agent 0.3.3 `checks.paths`, `checks.tunnel_logs`, tunnel byte counters).

`paths` holds, per listening port and peer, what `scripts/node/realuse.sh` prints: connections, MB acked per connection,
RTT and the retransmit share. The peer is another server of the workspace (a relay forwarding by DNAT), a tunnel or
loopback address, or "other" (users; never judged). On an exit, a relay peer whose connections move under
`quality_mb_min` MB each or retransmit above `quality_retrans_max` %, with at least `quality_min_conns` connections,
for QUALITY_HOLD_S, is `path_quality_low`; it clears after QUALITY_CLEAR_S of good samples.

A tunnel is unhealthy when its BackPack unit logged `tunnel_log_fails` handshake failures in 10 minutes, or when its
interface stopped receiving for `tunnel_flat_min` minutes while it still sends (one-sided) after it had carried traffic."""
from typing import Any, Dict, List, Optional, Tuple

from ..overview.detectors import make
from . import memory as m

QUALITY_HOLD_S = 600
QUALITY_CLEAR_S = 300
TX_RECENT_S = 300  # "still sends": its tx counter moved this recently
TUNNEL_KEEP = 100


def _num(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def by_peer(checks: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """The `paths` rows summed per peer over its ports (MB and retransmits weighted by connections); "other" left out."""
    out: Dict[str, Dict[str, Any]] = {}
    for r in m.dicts((checks or {}).get("paths")) or []:
        peer, port, n = m.text(r.get("peer"), 64), m.num(r.get("port")), m.num(r.get("conns"))
        mb, rtt, retrans = _num(r.get("mb_per_conn")), _num(r.get("rtt_ms")), _num(r.get("retrans_pct"))
        if not peer or peer == "other" or port is None or not n or n < 0 or mb is None:
            continue
        p = out.setdefault(peer, {"ports": [], "conns": 0, "mb": 0.0, "rtt": 0.0, "retrans": 0.0, "retrans_n": 0})
        p["ports"].append(port)
        p["conns"] += n
        p["mb"] += mb * n
        p["rtt"] += (rtt or 0.0) * n
        if retrans is not None:
            p["retrans"] += retrans * n
            p["retrans_n"] += n
    for p in out.values():
        n = p["conns"]
        p.update(mb_per_conn=round(p["mb"] / n, 3), rtt_ms=round(p["rtt"] / n, 1),
                 retrans_pct=round(p["retrans"] / p["retrans_n"], 1) if p["retrans_n"] else None)
    return out


def bad(p: Dict[str, Any], th: Dict[str, float]) -> Optional[bool]:
    """True below the quality floor, False above it, None with too few connections to say."""
    if p["conns"] < th["quality_min_conns"]:
        return None
    return p["mb_per_conn"] < th["quality_mb_min"] or (p["retrans_pct"] is not None and p["retrans_pct"] > th["quality_retrans_max"])


def observe(state: Dict[str, Any], checks: Optional[Dict[str, Any]], th: Dict[str, float], now: int) -> None:
    if not isinstance(checks, dict):
        return
    if isinstance(checks.get("paths"), list):
        old = state.get("quality") if isinstance(state.get("quality"), dict) else {}
        new = {}
        for peer, p in by_peer(checks).items():
            mem = old.get(peer) if isinstance(old.get(peer), dict) else {}
            b, since, good = bad(p, th), m.num(mem.get("bad_since")), m.num(mem.get("good_since"))
            if b:
                since, good = since or now, None
            elif b is False and since:
                good = good or now
                if now - good >= QUALITY_CLEAR_S:
                    since = good = None
            if since:
                new[peer] = {"bad_since": since, "good_since": good}
        state["quality"] = new
    tunnels = checks.get("tunnels") if isinstance(checks.get("tunnels"), dict) else None
    if tunnels is not None:
        old = state.get("tun") if isinstance(state.get("tun"), dict) else {}
        new = {}
        for iface, rx, tx in _ifaces(tunnels)[:TUNNEL_KEEP]:
            mem = old.get(iface) if isinstance(old.get(iface), dict) else {}
            prx, ptx = m.num(mem.get("rx")), m.num(mem.get("tx"))
            rx_at, tx_at, moved = m.num(mem.get("rx_at")) or now, m.num(mem.get("tx_at")) or now, mem.get("moved") is True
            if prx is not None and rx != prx:
                rx_at, moved = now, moved or rx > prx
            if ptx is not None and tx != ptx:
                tx_at = now
            if prx is not None and rx < prx:
                moved = False  # counters reset (reboot, recreated link): learn again
            new[iface] = {"rx": rx, "tx": tx, "rx_at": rx_at, "tx_at": tx_at, "moved": moved}
        state["tun"] = new


def _ifaces(tunnels: Dict[str, Any]) -> List[Tuple[str, int, int]]:
    seen: Dict[str, Tuple[str, int, int]] = {}
    for x in (m.dicts(tunnels.get("links")) or []) + (m.dicts(tunnels.get("configs")) or []):
        iface, rx, tx = m.text(x.get("iface"), 15), m.num(x.get("rx_bytes")), m.num(x.get("tx_bytes"))
        if iface and rx is not None and tx is not None:
            seen.setdefault(iface, (iface, rx, tx))
    return list(seen.values())


def _peer_label(peer: str, servers_by_ip: Dict[str, Any]) -> Tuple[str, Optional[Any]]:
    row = servers_by_ip.get(peer)
    return (row["alias"] or row["name"], row) if row is not None else (peer, None)


def issues(s, th: Dict[str, float], rep: Dict[str, Any], state: Dict[str, Any], ctx: Dict[str, Any], now: int) -> List[Dict[str, Any]]:
    checks = m.checks_of(rep)
    if checks is None:
        return []
    out: List[Dict[str, Any]] = []
    memo = state.get("quality") if isinstance(state.get("quality"), dict) else {}
    peers = by_peer(checks)
    servers_by_ip = ctx.get("servers_by_ip") or {}
    for peer, mem in sorted(memo.items()):
        since = m.num((mem or {}).get("bad_since")) if isinstance(mem, dict) else None
        p = peers.get(peer)
        if not th["on_path_quality_low"] or not since or now - since < QUALITY_HOLD_S or p is None:
            continue
        label, row = _peer_label(peer, servers_by_ip)
        if row is None and peer.startswith("127."):
            label = "تانل محلی (%s)" % peer
        out.append(make(s, "path_quality_low:%s" % peer, "warning", "کاربرانی که از مسیر %s می‌آیند تقریباً داده نمی‌گیرند" % label,
                        "اتصال‌ها برقرارند ولی هر کدام کمتر از حد داده جابه‌جا می‌کنند یا ارسال مجدد بالاست؛ پینگ و تست‌های مصنوعی "
                        "ممکن است سالم باشند. این رله را با تست داده بسنجید و اگر تأیید شد، تا رفع، از DNS لوکیشن بردارید (هر نام دو رلهٔ سالم).",
                        peer=peer, relay=label if row is not None else None, ports=["tcp/%d" % x for x in sorted(p["ports"])],
                        conns=p["conns"], mb_per_conn=p["mb_per_conn"], rtt_ms=p["rtt_ms"], retrans_pct=p["retrans_pct"],
                        held_s=now - since))
    out.extend(_tunnel_issues(s, th, checks, state, now))
    return out


def _tunnel_issues(s, th, checks, state, now) -> List[Dict[str, Any]]:
    if not th["on_tunnel_unhealthy"]:
        return []
    tunnels = checks.get("tunnels") if isinstance(checks.get("tunnels"), dict) else {}
    configs = m.dicts(tunnels.get("configs")) or []
    by_unit = {c.get("unit"): c for c in configs if isinstance(c.get("unit"), str)}
    found: Dict[str, Dict[str, Any]] = {}
    for r in m.dicts(checks.get("tunnel_logs")) or []:
        unit = m.text(r.get("unit"), 100)
        fails = (m.num(r.get("no_answer")) or 0) + (m.num(r.get("handshake_fail")) or 0)
        tag = m.num(r.get("wrong_tag")) or 0
        if unit and (fails >= th["tunnel_log_fails"] or tag > 0):
            c = by_unit.get(unit) or {}
            name = m.text(c.get("name"), 64) or unit.replace(".service", "")
            found.setdefault(name, {"unit": unit, "iface": m.text(c.get("iface"), 15)}).update(handshake_fails_10m=fails, wrong_tag_10m=tag)
    tun = state.get("tun") if isinstance(state.get("tun"), dict) else {}
    for iface, mem in tun.items():
        if not isinstance(mem, dict) or mem.get("moved") is not True:
            continue
        flat = now - (m.num(mem.get("rx_at")) or now)
        if flat >= th["tunnel_flat_min"] * 60 and now - (m.num(mem.get("tx_at")) or 0) <= TX_RECENT_S:
            c = next((x for x in configs if x.get("iface") == iface), {})
            name = m.text(c.get("name"), 64) or iface
            found.setdefault(name, {"unit": m.text(c.get("unit"), 100), "iface": iface}).update(rx_flat_s=flat)
    out = []
    for name, ev in sorted(found.items()):
        both = "rx_flat_s" in ev and ("handshake_fails_10m" in ev)
        out.append(make(s, "tunnel_unhealthy:%s" % name, "critical" if both else "warning", "تانل %s سالم نیست" % name,
                        "واحد تانل ممکن است active بماند در حالی که مسیر مرده است؛ لاگ آن خطای handshake دارد یا رابط تانل فقط می‌فرستد و چیزی نمی‌گیرد. "
                        "پینگ سیل‌آسا به سر دیگر تانل بزنید و allowlist رله (فهرست منابع مورد اعتماد) را بررسی کنید.",
                        tunnel=name, **{k: v for k, v in ev.items() if v is not None}))
    return out
