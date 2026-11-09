"""Config drift (agent 0.3.3 `checks.drift`): the live ipset, DNAT and sysctl state against the files that rebuild it.

The agent ships counts, short hashes, port numbers and sysctl values only, never the lists. A difference must hold
for DRIFT_HOLD_S with the same numbers before it is an issue: an edit in progress, or a reload a minute later, is not
drift. Typical cases from the field: an access list edited without restarting the service that loads it (8 trusted
sources live, 21 in the file), a DNAT rule changed by hand and not in the boot file, a sysctl file that the kernel
ignored at boot (incident 74)."""
import json
from typing import Any, Dict, List, Optional, Tuple

from ..overview.detectors import make
from . import memory as m

DRIFT_HOLD_S = 600  # two runs of the 5-minute collector


def _rows(drift: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    return m.dicts(drift.get(key)) or []


def findings(checks: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """code -> what differs now; empty when the report has no drift block."""
    drift = (checks or {}).get("drift")
    if not isinstance(drift, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    sets = []
    for r in _rows(drift, "ipset"):
        live, have = m.num(r.get("live")), m.num(r.get("file"))
        name, source = m.text(r.get("set"), 31), m.text(r.get("source"), 200)
        if name and source and live is not None and have is not None and live != have:
            sets.append({"set": name, "live": live, "file": have, "source": source})
    if sets:
        out["drift_ipset"] = {"sets": sets}
    tables = []
    for r in _rows(drift, "dnat"):
        table, live, have = m.text(r.get("table"), 64), m.num(r.get("live")), m.num(r.get("file_rules"))
        if not table or live is None:
            continue
        ports = [p for p in r.get("ports") or [] if m.num(p) is not None][:50] if isinstance(r.get("ports"), list) else []
        if have is None and live > 0:
            tables.append({"table": table, "live": live, "file": None, "path": None, "ports": []})
        elif have is not None and (live != have or r.get("live_hash") != r.get("file_hash")):
            tables.append({"table": table, "live": live, "file": have, "path": m.text(r.get("file"), 200), "ports": ports})
    if tables:
        out["drift_dnat"] = {"tables": tables}
    sc = drift.get("sysctl") if isinstance(drift.get("sysctl"), dict) else {}
    keys = []
    for r in _rows(sc, "mismatch"):
        key, live, want = m.text(r.get("key"), 100), m.text(r.get("live"), 64), m.text(r.get("file"), 64)
        if key and live is not None and want is not None:
            keys.append({"key": key, "live": live, "file": want, "source": m.text(r.get("source"), 200)})
    if keys:
        out["drift_sysctl"] = {"keys": keys[:50], "checked": m.num(sc.get("checked"))}
    return out


def observe(state: Dict[str, Any], checks: Optional[Dict[str, Any]], now: int) -> None:
    """Remember since when each finding has held with the same numbers (a new number starts the clock again)."""
    if not isinstance((checks or {}).get("drift"), dict):
        return
    old = state.get("drift") if isinstance(state.get("drift"), dict) else {}
    new = {}
    for code, found in findings(checks).items():
        sig = json.dumps(found, sort_keys=True)
        prev = old.get(code) if isinstance(old.get(code), dict) else {}
        new[code] = {"sig": sig, "since": m.num(prev.get("since")) if prev.get("sig") == sig and m.num(prev.get("since")) else now}
    state["drift"] = new


def _held(state: Dict[str, Any], code: str, found: Dict[str, Any], now: int) -> Optional[int]:
    mem = (state.get("drift") or {}).get(code) if isinstance(state.get("drift"), dict) else None
    if not isinstance(mem, dict) or mem.get("sig") != json.dumps(found, sort_keys=True):
        return None
    since = m.num(mem.get("since"))
    return now - since if since is not None and now - since >= DRIFT_HOLD_S else None


def _biggest(items: List[Dict[str, Any]]) -> Tuple[Any, Any]:
    top = max(items, key=lambda x: abs((x["live"] or 0) - (x["file"] or 0)))
    return top["live"], top["file"]


def issues(s, th: Dict[str, float], rep: Dict[str, Any], state: Dict[str, Any], now: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for code, found in findings(m.checks_of(rep)).items():
        held = _held(state, code, found, now)
        if held is None or not th["on_" + code]:
            continue
        if code == "drift_ipset":
            sets = found["sets"]
            live, have = _biggest(sets)
            fewer = any(x["live"] < x["file"] for x in sets)
            out.append(make(s, "drift_ipset", "warning" if fewer else "info",
                            "مجموعهٔ ipset زنده با فهرست دسترسی در فایل یکی نیست",
                            "سرویسی که ipset را از فایل می‌سازد فایل را فقط هنگام شروع می‌خواند؛ پس از ویرایش فایل باید ری‌استارت شود "
                            "(مثلاً systemctl restart nyxon-access) و بعد شمار اعضای ipset با فایل برابر باشد.",
                            live=live, file=have, sets=["%s: %d / %d (%s)" % (x["set"], x["live"], x["file"], x["source"]) for x in sets],
                            held_s=held))
        elif code == "drift_dnat":
            tables = found["tables"]
            unsaved = [t for t in tables if t["file"] is None]
            live, have = tables[0]["live"], tables[0]["file"]
            out.append(make(s, "drift_dnat", "warning", "قوانین DNAT زنده با فایل بوت یکی نیست",
                            "قانونی که فقط زنده عوض شده با اولین ریبوت یا ری‌استارت سرویس DNAT برمی‌گردد. فایل /etc/nftables-*.nft را با "
                            "قوانین درست هم‌سان کنید، با nft -c -f بسنجید و با تأیید مالک بارگذاری کنید.",
                            live=live, file=have, tables=["%s: %d / %s" % (t["table"], t["live"], "-" if t["file"] is None else t["file"])
                                                          for t in tables],
                            ports=["tcp/%d" % p for t in tables for p in t["ports"]][:50], without_file=[t["table"] for t in unsaved],
                            held_s=held))
        else:
            keys = found["keys"]
            out.append(make(s, "drift_sysctl", "warning", "مقدار زندهٔ sysctl با فایل‌های sysctl یکی نیست",
                            "کرنل مقدار فایل را اعمال نکرده (مثلاً ماژول conntrack پس از sysctl بارگذاری شده) یا کسی آن را زنده عوض کرده است. "
                            "با تأیید مالک sysctl --system بزنید و ماژول‌ها را در modules-load.d زود بارگذاری کنید.",
                            keys=[k["key"] for k in keys], values=["%s: %s / %s" % (k["key"], k["live"], k["file"]) for k in keys],
                            sources=sorted({k["source"] for k in keys if k["source"]}), checked=found["checked"], held_s=held))
    return out
