#!/usr/bin/env python3
"""DowntimeLess agent: standard-library collector and whitelisted job runner."""
import argparse
import concurrent.futures
import http.client
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

VERSION = "0.1.0"
UA = "DowntimeLess-Agent/" + VERSION
SELF_PATH = os.path.realpath(__file__)
GEO_URLS = ("https://ipinfo.io/json", "https://ipwho.is/")
GEO_TTL_S = 6 * 3600
GEO_RETRY_S = 900
MUTATING = ("apt_upgrade_safe", "reboot", "self_update")
HOLD_PKGS = ("docker-ce", "docker-ce-cli", "containerd.io", "docker-compose-plugin", "docker-buildx-plugin")
# Hold only what is not held already, and release only our own holds afterwards.
APT_SCRIPT = """
mine=""
held=$(apt-mark showhold)
for p in {pkgs}; do
  dpkg -s "$p" >/dev/null 2>&1 || continue
  echo "$held" | grep -qx "$p" && continue
  apt-mark hold "$p" >/dev/null && mine="$mine $p"
done
apt-get update -qq && apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold upgrade
rc=$?
[ -n "$mine" ] && apt-mark unhold $mine >/dev/null
exit $rc
"""


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def config_path():
    return os.environ.get("DL_AGENT_CONFIG", "/etc/downtimeless/agent.json")


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


# ---- parsers (pure: take file text) ----

def parse_cpu(text):
    """Return (total, idle, steal) jiffies from the aggregate cpu line."""
    for line in text.splitlines():
        if line.startswith("cpu "):
            v = [int(x) for x in line.split()[1:]]
            v += [0] * (8 - len(v))
            # guest time is already counted inside user/nice, so only the first 8 columns
            return sum(v[:8]), v[3] + v[4], v[7]
    return None


def cpu_usage(a, b):
    total = b[0] - a[0]
    if total <= 0:
        return 0.0, 0.0
    busy = 100.0 * (total - (b[1] - a[1])) / total
    steal = 100.0 * (b[2] - a[2]) / total
    return round(min(max(busy, 0.0), 100.0), 1), round(min(max(steal, 0.0), 100.0), 1)


def parse_meminfo(text):
    kb = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts:
            kb[key] = int(parts[0])
    if "MemTotal" not in kb:
        return None
    return kb["MemTotal"] // 1024, kb.get("MemAvailable", kb.get("MemFree", 0)) // 1024


def parse_first_float(text):
    parts = text.split()
    return float(parts[0]) if parts else None


def parse_tcp_snmp(text):
    """Return (OutSegs, RetransSegs) from /proc/net/snmp."""
    rows = [line.split()[1:] for line in text.splitlines() if line.startswith("Tcp:")]
    if len(rows) < 2:
        return None
    d = dict(zip(rows[0], rows[1]))
    return int(d["OutSegs"]), int(d["RetransSegs"])


def retrans_pct(prev, cur):
    out, retr = cur[0] - prev[0], cur[1] - prev[1]
    if out <= 0 or retr < 0:
        return 0.0
    return round(100.0 * retr / out, 2)


def parse_default_iface(route_text):
    """Lowest-metric default route from /proc/net/route."""
    best = None
    for line in route_text.splitlines()[1:]:
        f = line.split()
        if len(f) >= 8 and f[1] == "00000000" and f[7] == "00000000":
            if best is None or int(f[6]) < best[0]:
                best = (int(f[6]), f[0])
    return best[1] if best else None


def parse_ip_route(text):
    m = re.search(r"^default\b.*?\bdev (\S+)", text, re.M)
    return m.group(1) if m else None


def conntrack_pct(count_text, max_text):
    try:
        count, limit = int(count_text), int(max_text)
    except ValueError:
        return None
    return round(100.0 * count / limit, 1) if limit > 0 else None


def parse_failed_units(text):
    units = []
    for line in text.splitlines():
        f = line.split()
        if f and f[0] in ("●", "×", "*"):
            f = f[1:]
        if f:
            units.append(f[0])
    return units


def parse_ping(text):
    """Return (loss_pct, avg_rtt_ms); rtt is None when nothing came back."""
    m = re.search(r"([\d.]+)% packet loss", text)
    loss = float(m.group(1)) if m else 100.0
    r = re.search(r"= [\d.]+/([\d.]+)/", text)
    return loss, float(r.group(1)) if r else None


def parse_ipinfo(d):
    if not d.get("ip"):
        return None
    org = re.sub(r"^AS\d+\s+", "", d.get("org") or "")
    return d["ip"], {"country": d.get("country"), "city": d.get("city"), "org": org or None}


def parse_ipwho(d):
    if not d.get("success", True) or not d.get("ip"):
        return None
    conn = d.get("connection") or {}
    org = conn.get("org") or conn.get("isp")
    return d["ip"], {"country": d.get("country_code"), "city": d.get("city"), "org": org}


# ---- HTTP ----

def http_call(url, body=None, key=None, max_bytes=8 << 20):
    """GET, or POST of a JSON body; 10s to connect, 30s per read (urllib cannot split them)."""
    u = urllib.parse.urlsplit(url)
    cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
    headers = {"User-Agent": UA}
    if key:
        headers["X-Agent-Key"] = key
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    conn = cls(u.netloc, timeout=10)
    try:
        conn.connect()
        conn.sock.settimeout(30)
        target = (u.path or "/") + ("?" + u.query if u.query else "")
        conn.request("POST" if data is not None else "GET", target, data, headers)
        r = conn.getresponse()
        payload = r.read(max_bytes)
        if r.status != 200:
            raise RuntimeError("HTTP %d from %s" % (r.status, u.netloc))
        return payload
    finally:
        conn.close()


def http_json(url, body, key=None):
    return json.loads(http_call(url, body, key))


def fetch_text(url, timeout=10, limit=1 << 16):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limit).decode("utf-8", "replace")


# ---- collectors ----

def lookup_geo():
    for url, parse in zip(GEO_URLS, (parse_ipinfo, parse_ipwho)):
        try:
            found = parse(json.loads(fetch_text(url)))
        except Exception:
            continue
        if found:
            return found
    return None


def geo_cached(state):
    now = time.monotonic()
    if now >= state.get("geo_next", 0):
        found = lookup_geo()
        if found:
            state["geo"] = found
        # a failed lookup retries sooner than a good one, so a boot-time network blip heals
        state["geo_next"] = now + (GEO_TTL_S if found else GEO_RETRY_S)
    return state.get("geo", (None, None))


def default_iface():
    iface = parse_default_iface(read("/proc/net/route"))
    if iface:
        return iface
    try:
        out = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_ip_route(out)


def sample():
    iface = default_iface()
    nic = None
    if iface:
        base = "/sys/class/net/%s/statistics/" % iface
        try:
            nic = (int(read(base + "rx_bytes")), int(read(base + "tx_bytes")))
        except ValueError:
            pass
    return {
        "mono": time.monotonic(),
        "cpu": parse_cpu(read("/proc/stat")),
        "snmp": parse_tcp_snmp(read("/proc/net/snmp")),
        "iface": iface,
        "nic": nic,
    }


def bps(prev, cur, dt):
    if cur < prev or dt <= 0:
        return 0
    return int((cur - prev) * 8 / dt)


def failed_units():
    try:
        out = subprocess.run(["systemctl", "--failed", "--no-legend", "--plain"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_failed_units(out)


def valid_host(t):
    return isinstance(t, str) and re.fullmatch(r"[A-Za-z0-9:][A-Za-z0-9.:_-]{0,252}", t) is not None


def tcp_ping(host, port, timeout=3.0):
    start = time.perf_counter()
    try:
        socket.create_connection((host, port), timeout=timeout).close()
    except OSError:
        return 100.0, None
    return 0.0, round((time.perf_counter() - start) * 1000, 1)


def icmp_ping(host):
    try:
        out = subprocess.run(["ping", "-c", "5", "-W", "1", "-i", "0.3", host],
                             capture_output=True, text=True, timeout=12).stdout
    except (OSError, subprocess.SubprocessError):
        return 100.0, None
    return parse_ping(out)


def check_target(item):
    target, port = item.get("target"), item.get("tcp_port")
    if not valid_host(target):
        loss, rtt = 100.0, None
    elif port:
        loss, rtt = tcp_ping(target, int(port))
    else:
        loss, rtt = icmp_ping(target)
    return {"target": target, "loss_pct": loss, "rtt_ms": rtt}


def run_pings(items, budget=20.0):
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=8)
    futures = [pool.submit(check_target, i) for i in items]
    done, _ = concurrent.futures.wait(futures, timeout=budget)
    pool.shutdown(wait=False)
    out = []
    for item, fut in zip(items, futures):
        if fut in done and fut.exception() is None:
            out.append(fut.result())
        else:
            out.append({"target": item.get("target"), "loss_pct": 100.0, "rtt_ms": None})
    return out


def build_report(state):
    a = sample()
    time.sleep(1)
    b = sample()
    prev = state.get("prev") or a
    state["prev"] = b
    dt = b["mono"] - prev["mono"]

    cpu = steal = None
    if a["cpu"] and b["cpu"]:
        cpu, steal = cpu_usage(a["cpu"], b["cpu"])
    mem = parse_meminfo(read("/proc/meminfo"))
    retrans = retrans_pct(prev["snmp"], b["snmp"]) if prev["snmp"] and b["snmp"] else None
    net = None
    if b["nic"]:
        pn = prev["nic"] if prev["iface"] == b["iface"] and prev["nic"] else b["nic"]
        net = {"iface": b["iface"], "rx_bytes": b["nic"][0], "tx_bytes": b["nic"][1],
               "rx_bps": bps(pn[0], b["nic"][0], dt), "tx_bps": bps(pn[1], b["nic"][1], dt)}
    disk_total = disk_used = None
    try:
        st = os.statvfs("/")
        disk_total = round(st.f_blocks * st.f_frsize / 1024 ** 3, 1)
        disk_used = round((st.f_blocks - st.f_bfree) * st.f_frsize / 1024 ** 3, 1)
    except OSError:
        pass
    uptime = parse_first_float(read("/proc/uptime"))
    ip, geo = geo_cached(state)

    return {
        "agent_version": VERSION,
        "ts": int(time.time()),
        "hostname": socket.gethostname(),
        "public_ip": ip,
        "geo": geo,
        "uptime_s": int(uptime) if uptime is not None else None,
        "cpu_pct": cpu, "steal_pct": steal, "load1": parse_first_float(read("/proc/loadavg")),
        "ram_total_mb": mem[0] if mem else None, "ram_avail_mb": mem[1] if mem else None,
        "disk_total_gb": disk_total, "disk_used_gb": disk_used,
        "net": net,
        "tcp_retrans_pct": retrans,
        "conntrack_pct": conntrack_pct(read("/proc/sys/net/netfilter/nf_conntrack_count"),
                                       read("/proc/sys/net/netfilter/nf_conntrack_max")),
        "failed_units": failed_units(),
        "reboot_required": os.path.exists("/var/run/reboot-required"),
        "ping": run_pings(state["ping_targets"]),
        "jobs_done": list(state["jobs_done"]),
    }


# ---- jobs ----

def http_url(value):
    u = urllib.parse.urlsplit(value if isinstance(value, str) else "")
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError("args.url must be an http(s) URL")
    return value


def job_ping(args, state):
    target = args.get("target")
    if not valid_host(target):
        raise ValueError("invalid target")
    loss, rtt = icmp_ping(target)
    return {"loss_pct": loss, "rtt_ms": rtt}


def job_tcp_check(args, state):
    target, port = args.get("target"), args.get("port")
    if not valid_host(target) or not isinstance(port, int) or not 0 < port < 65536:
        raise ValueError("invalid target or port")
    loss, rtt = tcp_ping(target, port)
    return {"open": loss == 0, "rtt_ms": rtt}


def job_speedtest_down(args, state):
    req = urllib.request.Request(http_url(args.get("url")), headers={"User-Agent": UA})
    start, got = time.monotonic(), 0
    with urllib.request.urlopen(req, timeout=25) as r:
        while time.monotonic() - start < 25:
            chunk = r.read(65536)
            if not chunk:
                break
            got += len(chunk)
    if got == 0:
        raise RuntimeError("no data received")
    return {"mbps": round(got * 8 / (time.monotonic() - start) / 1e6, 2)}


def job_speedtest_up(args, state):
    data = bytes(10 * 1024 * 1024)
    req = urllib.request.Request(http_url(args.get("url")), data=data, method="POST",
                                 headers={"User-Agent": UA, "Content-Type": "application/octet-stream"})
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=25) as r:
        r.read(1024)
    return {"mbps": round(len(data) * 8 / (time.monotonic() - start) / 1e6, 2)}


def systemd_run(argv):
    out = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError((out.stderr or out.stdout).strip()[:200] or "systemd-run failed")


def job_apt_upgrade_safe(args, state):
    # runs detached so a long upgrade cannot stall reporting; reboot_required in later reports is the outcome signal
    systemd_run(["systemd-run", "--unit=dl-apt-upgrade", "--collect",
                 "--setenv=DEBIAN_FRONTEND=noninteractive", "--setenv=NEEDRESTART_MODE=l",
                 "/bin/sh", "-c", APT_SCRIPT.format(pkgs=" ".join(HOLD_PKGS))])
    return {"unit": "dl-apt-upgrade", "started": True}


def job_reboot(args, state):
    systemd_run(["systemd-run", "--on-active=5", "systemctl", "reboot"])
    state["flush"] = True  # report ok before the timer fires
    return {"in_s": 5}


def job_self_update(args, state):
    src = http_call(state["master"] + "/agent/agent.py", max_bytes=2 << 20)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(SELF_PATH), prefix=".agent-", suffix=".py")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(src)
        compile(src, tmp, "exec")
        out = subprocess.run([sys.executable, tmp, "version"], capture_output=True, text=True, timeout=15)
        new = out.stdout.strip()
        if out.returncode != 0 or not re.fullmatch(r"\d+\.\d+\.\d+", new):
            raise RuntimeError("downloaded agent failed the version check")
        os.chmod(tmp, 0o755)
        os.replace(tmp, SELF_PATH)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    state["restart"] = True
    state["flush"] = True
    return {"from": VERSION, "to": new}


JOBS = {
    "ping": job_ping,
    "tcp_check": job_tcp_check,
    "speedtest_down": job_speedtest_down,
    "speedtest_up": job_speedtest_up,
    "apt_upgrade_safe": job_apt_upgrade_safe,
    "reboot": job_reboot,
    "self_update": job_self_update,
}


def run_job(job, state):
    kind = job.get("kind")
    res = {"id": job.get("id"), "status": "ok", "result": {}, "error": None}
    if kind not in JOBS:
        res.update(status="rejected", error="unknown job kind")
    elif kind in MUTATING and state["permission"] not in ("safe", "full"):
        res.update(status="rejected", error="permission level does not allow this job")
    else:
        try:
            res["result"] = JOBS[kind](job.get("args") or {}, state)
        except Exception as e:
            res.update(status="error", error=("%s: %s" % (type(e).__name__, e))[:300])
    return res


# ---- main loop ----

def new_state(cfg):
    return {"master": cfg["master"], "key": cfg["agent_key"], "permission": cfg.get("permission", "none"),
            "ping_targets": [], "jobs_done": [], "flush": False, "restart": False}


def run_cycle(state):
    body = build_report(state)
    resp = http_json(state["master"] + "/api/agent/v1/report", body, state["key"])
    del state["jobs_done"][:len(body["jobs_done"])]
    if isinstance(resp.get("permission"), str):
        state["permission"] = resp["permission"]
    state["ping_targets"] = [t for t in resp.get("ping_targets") or [] if isinstance(t, dict)]
    if not state["restart"]:
        for job in resp.get("jobs") or []:
            state["jobs_done"].append(run_job(job, state))
        del state["jobs_done"][:-100]
    return min(max(int(resp.get("interval_s") or 30), 5), 600)


def load_config():
    try:
        cfg = json.loads(read(config_path()))
        cfg["master"] = cfg["master"].rstrip("/")
        cfg["agent_key"]
    except (ValueError, KeyError, AttributeError, TypeError):
        sys.exit("agent: missing or invalid config %s (run enroll first)" % config_path())
    return cfg


def cmd_run(args):
    state = new_state(load_config())
    fails, wait = 0, 0
    while True:
        try:
            wait = run_cycle(state)
            fails = 0
        except Exception as e:
            fails += 1
            wait = min(60, 5 * 2 ** (fails - 1))
            log("report failed (%d): %s" % (fails, e))
        if state["restart"] and not state["jobs_done"]:
            log("restarting after self_update")
            sys.exit(0)
        if state["flush"] and not fails:
            wait = 1
        state["flush"] = False
        time.sleep(wait)


def cmd_once(args):
    state = {"permission": "none", "ping_targets": [], "jobs_done": []}
    print(json.dumps(build_report(state), indent=2))


def write_config(cfg):
    path = config_path()
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def cmd_enroll(args):
    master = args.master.rstrip("/")
    try:
        resp = http_json(master + "/api/agent/v1/enroll", {"token": args.token, "hostname": socket.gethostname()})
        key = resp["agent_key"]
        if not isinstance(key, str) or not key:
            raise ValueError("empty agent_key")
    except Exception as e:
        sys.exit("agent: enroll failed: %s" % e)
    write_config({"master": master, "agent_key": key})
    print("enrolled, config written to " + config_path())


def main(argv=None):
    p = argparse.ArgumentParser(prog="agent.py", description="DowntimeLess agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run").set_defaults(fn=cmd_run)
    sub.add_parser("once").set_defaults(fn=cmd_once)
    sub.add_parser("version").set_defaults(fn=lambda a: print(VERSION))
    e = sub.add_parser("enroll")
    e.add_argument("--master", required=True)
    e.add_argument("--token", required=True)
    e.set_defaults(fn=cmd_enroll)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
