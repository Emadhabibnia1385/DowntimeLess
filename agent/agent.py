#!/usr/bin/env python3
"""DowntimeLess agent: standard-library collector and whitelisted job runner."""
import argparse
import calendar
import concurrent.futures
import contextlib
import http.client
import ipaddress
import json
import glob
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "0.3.1"
UA = "DowntimeLess-Agent/" + VERSION
SELF_PATH = os.path.realpath(__file__)
# With no address they describe the caller's outbound address; with one, that address itself.
GEO_URLS = (
    lambda ip: "https://ipinfo.io/%sjson" % (ip + "/" if ip else ""),
    lambda ip: "https://ipwho.is/" + ip,
)
GEO_TTL_S = 6 * 3600
GEO_RETRY_S = 900
SSL_TTL_S = 1800
CERT_GLOBS = ("/etc/letsencrypt/live/*/cert.pem", "/root/.acme.sh/*/*.cer")
# PasarGuard node certificates (/var/lib/<node>/certs): listed apart, the master offers no certbot action on them
NODE_CERT_GLOBS = ("/var/lib/*/certs/ssl_cert.pem",)
ACME_SKIP = ("ca.cer", "fullchain.cer")
# a folder like "example.com.bak-20261103" is a backup of a certificate, not one
BACKUP_RE = re.compile(r"\.bak|\.old$|\.orig$|backup", re.I)
CERT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
# self_update only swaps this file for the master's copy, so it needs no permission level (the master agrees)
MUTATING = ("apt_upgrade_safe", "reboot", "cert_renew", "cert_delete", "service_restart", "vacuum_logs")
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


def parse_swap(text):
    kb = {}
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if parts and parts[0].isdigit():
            kb[key] = int(parts[0])
    if not kb.get("SwapTotal"):
        return None
    return kb["SwapTotal"] // 1024, (kb["SwapTotal"] - kb.get("SwapFree", 0)) // 1024


def parse_os_release(text):
    for line in text.splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"') or None
    return None


def parse_cpu_model(text):
    m = re.search(r"(?m)^(?:model name|Model|Hardware)\s*:\s*(.+)$", text)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def parse_loadavg(text):
    try:
        return tuple(float(x) for x in text.split()[:3]) if len(text.split()) >= 3 else None
    except ValueError:
        return None


def parse_curr_estab(snmp_text):
    """Established TCP connections: the CurrEstab column of the Tcp: lines of /proc/net/snmp."""
    rows = [line.split() for line in snmp_text.splitlines() if line.startswith("Tcp:")]
    if len(rows) < 2 or "CurrEstab" not in rows[0]:
        return None
    try:
        return int(rows[1][rows[0].index("CurrEstab")])
    except (IndexError, ValueError):
        return None


def parse_ipv6(text):
    m = re.search(r"inet6\s+([0-9a-fA-F:]+)/\d+\s+scope global", text)
    return m.group(1).lower() if m else None


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

@contextlib.contextmanager
def ipv4_only():
    """Name lookups answer IPv4 only inside the block, so a lookup service sees our IPv4 address."""
    real = socket.getaddrinfo

    def v4(host, port, family=0, *args, **kwargs):
        return real(host, port, socket.AF_INET, *args, **kwargs)

    socket.getaddrinfo = v4
    try:
        yield
    finally:
        socket.getaddrinfo = real


def local_ipv4():
    """The IPv4 address the default route leaves from, or None; sends no packet."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
    except OSError:
        return None


def global_local_ipv4():
    local = local_ipv4()
    try:
        return local if local and ipaddress.ip_address(local).is_global else None
    except ValueError:
        return None


def own_ipv4(looked_up):
    """The server's own address when it is public (that is what people log in to), else the looked-up one."""
    return global_local_ipv4() or (looked_up if looked_up and ":" not in looked_up else None)


def lookup_geo(ip=""):
    for url, parse in zip(GEO_URLS, (parse_ipinfo, parse_ipwho)):
        try:
            with ipv4_only():
                found = parse(json.loads(fetch_text(url(ip))))
        except Exception:
            continue
        if found:
            return found
    return None


def geo_cached(state):
    now = time.monotonic()
    if now >= state.get("geo_next", 0):
        # place the server by its own address: a relay can exit the internet through a foreign transit
        found = lookup_geo(global_local_ipv4() or "")
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
    # the read-only checks run in the background during the sampling pause and the pings
    checks_at = start_checks(state)
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
    load = parse_loadavg(read("/proc/loadavg"))
    swap = parse_swap(read("/proc/meminfo"))
    looked_up, geo = geo_cached(state)
    ip = own_ipv4(looked_up)

    return {
        "agent_version": VERSION,
        "ts": int(time.time()),
        "hostname": socket.gethostname(),
        "public_ip": ip,
        "geo": geo,
        "uptime_s": int(uptime) if uptime is not None else None,
        "cpu_cores": os.cpu_count(),
        "cpu_pct": cpu, "steal_pct": steal, "load1": load[0] if load else None,
        "load5": load[1] if load else None, "load15": load[2] if load else None,
        "swap_total_mb": swap[0] if swap else None, "swap_used_mb": swap[1] if swap else None,
        "tcp_established": parse_curr_estab(read("/proc/net/snmp")),
        "info": system_info(state, uptime),
        "ram_total_mb": mem[0] if mem else None, "ram_avail_mb": mem[1] if mem else None,
        "disk_total_gb": disk_total, "disk_used_gb": disk_used,
        "net": net,
        "tcp_retrans_pct": retrans,
        "conntrack_pct": conntrack_pct(read("/proc/sys/net/netfilter/nf_conntrack_count"),
                                       read("/proc/sys/net/netfilter/nf_conntrack_max")),
        "failed_units": failed_units(),
        "reboot_required": os.path.exists("/var/run/reboot-required"),
        "ssl": ssl_cached(state),
        "ping": run_pings(state["ping_targets"]),
        "jobs_done": list(state["jobs_done"]),
        **acct_fields(state),
        **checks_fields(state, checks_at),
    }


# ---- link accounting: counter-only nftables table, one in/out counter per peer server ----

ACCT_TABLE = "dl_acct"
ACCT_MAX_PEERS = 64


def acct_peers(values):
    """The valid, unique IPv4 peers out of what the master sent."""
    out = []
    for v in values if isinstance(values, list) else []:
        if not isinstance(v, str):
            continue
        try:
            ip = str(ipaddress.IPv4Address(v))
        except (ValueError, TypeError):
            continue
        if ip not in out:
            out.append(ip)
    return out[:ACCT_MAX_PEERS]


def acct_ruleset(peers):
    """A table that only counts: it never accepts, drops or changes a packet (policy accept, counters only).

    Inbound is counted before NAT (source = peer), outbound after NAT (destination = peer), so traffic that
    this server forwards or tunnels to a peer is counted too.
    """
    pre = "\n".join('    ip saddr %s counter comment "dl:in:%s"' % (ip, ip) for ip in peers)
    post = "\n".join('    ip daddr %s counter comment "dl:out:%s"' % (ip, ip) for ip in peers)
    return (
        "add table inet %(t)s\ndelete table inet %(t)s\n"
        "table inet %(t)s {\n"
        "  chain dl_in { type filter hook prerouting priority -300; policy accept;\n%(pre)s\n  }\n"
        "  chain dl_out { type filter hook postrouting priority 300; policy accept;\n%(post)s\n  }\n}\n"
    ) % {"t": ACCT_TABLE, "pre": pre, "post": post}


def parse_acct(text):
    """{ip: {"in": bytes, "out": bytes}} from `nft -j list table`; None when the text is not that listing."""
    try:
        items = json.loads(text)["nftables"]
    except (ValueError, KeyError, TypeError):
        return None
    out = {}
    for item in items:
        rule = item.get("rule") if isinstance(item, dict) else None
        if not rule:
            continue
        m = re.fullmatch(r"dl:(in|out):(\d+\.\d+\.\d+\.\d+)", str(rule.get("comment") or ""))
        if not m:
            continue
        for expr in rule.get("expr") or []:
            counter = expr.get("counter") if isinstance(expr, dict) else None
            if isinstance(counter, dict) and isinstance(counter.get("bytes"), int):
                out.setdefault(m.group(2), {"in": 0, "out": 0})[m.group(1)] = counter["bytes"]
    return out


def nft_run(args, text=None):
    r = subprocess.run(["nft"] + args, input=text, capture_output=True, text=True, timeout=15)
    return r.returncode, (r.stdout if r.returncode == 0 else r.stderr).strip()


def acct_remove(state):
    if shutil.which("nft"):
        nft_run(["delete", "table", "inet", ACCT_TABLE])
    state["acct_sig"] = None


def acct_fields(state):
    counters, error = acct_report(state)
    out = {}
    if counters is not None:
        out["acct"] = counters
    if error:
        out["acct_error"] = error
    return out


def acct_report(state):
    """Keeps the counting table in step with the peers the master asks for and returns its counters."""
    peers = acct_peers(state.get("acct_peers"))
    if not peers:
        if state.get("acct_sig") is not None or not state.get("acct_checked"):
            state["acct_checked"] = True
            try:
                acct_remove(state)
            except (OSError, subprocess.SubprocessError) as e:
                log("acct remove failed: %s" % e)
        return None, None
    state["acct_checked"] = True
    if not shutil.which("nft"):
        return None, "nft is not installed on this server"
    sig = tuple(sorted(peers))
    try:
        for attempt in (1, 2):
            if state.get("acct_sig") != sig or attempt == 2:
                script = acct_ruleset(peers)
                code, msg = nft_run(["-c", "-f", "-"], script)
                if code == 0:
                    code, msg = nft_run(["-f", "-"], script)
                if code != 0:
                    state["acct_sig"] = None
                    return None, ("nft refused the counting table: %s" % msg)[:200]
                state["acct_sig"] = sig
            code, text = nft_run(["-j", "list", "table", "inet", ACCT_TABLE])
            counters = parse_acct(text) if code == 0 else None
            if counters is not None:
                return counters, None
            state["acct_sig"] = None  # the table vanished (a ruleset flush): build it again once
        return None, "counting table could not be read"
    except (OSError, subprocess.SubprocessError) as e:
        return None, ("%s: %s" % (type(e).__name__, e))[:200]


# ---- system info ----

def system_info(state, uptime):
    """What the server is: system, kernel, CPU model, boot time, IPv6 address (slow-changing, cached)."""
    now = time.time()
    if now - state.get("ipv6_at", 0) > 600:
        state["ipv6"] = parse_ipv6(run_text(["ip", "-6", "-o", "addr", "show", "scope", "global"], timeout=5))
        state["ipv6_at"] = now
    return {
        "os": parse_os_release(read("/etc/os-release")),
        "kernel": platform.release() or None,
        "cpu_model": parse_cpu_model(read("/proc/cpuinfo")),
        "cpu_cores": os.cpu_count(),
        "boot_ts": int(now - uptime) if uptime is not None else None,
        "ipv6": state.get("ipv6"),
    }


# ---- ssl ----

def parse_cert_end(text):
    m = re.search(r"notAfter=(.+)", text)
    if not m:
        return None
    try:
        return calendar.timegm(time.strptime(m.group(1).strip(), "%b %d %H:%M:%S %Y %Z"))
    except ValueError:
        return None


def parse_cert_names(text):
    return re.findall(r"DNS:([^\s,]+)", text)


def run_text(argv, timeout=10):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def read_cert(path, now):
    out = run_text(["openssl", "x509", "-noout", "-enddate", "-ext", "subjectAltName", "-in", path])
    end = parse_cert_end(out)
    if end is None:
        return None
    source = "acme.sh" if "/.acme.sh/" in path else "certbot"
    name = os.path.basename(os.path.dirname(path)).replace("_ecc", "")
    return {"name": name, "source": source, "domains": parse_cert_names(out) or [name],
            "not_after": end, "days_left": int((end - now) // 86400)}


def renew_status():
    def unit(verb, name):
        return run_text(["systemctl", verb, name]).strip()
    crontab = run_text(["crontab", "-l"])
    return {
        "certbot_installed": bool(shutil.which("certbot")) or os.path.isdir("/etc/letsencrypt"),
        "certbot_timer_enabled": unit("is-enabled", "certbot.timer") == "enabled",
        "certbot_timer_active": unit("is-active", "certbot.timer") == "active",
        "certbot_last_run_failed": unit("is-failed", "certbot.service") == "failed",
        "certbot_cron": os.path.exists("/etc/cron.d/certbot"),
        "acme_sh_cron": "acme.sh" in crontab,
    }


def nginx_domains(config):
    """Public host names that a TLS server block of the nginx config answers for."""
    names = set()
    config = re.sub(r"(?m)#.*$", "", config)
    for block in re.split(r"\bserver\s*\{", config)[1:]:
        if not (re.search(r"\blisten\s+[^;]*\b443\b", block) or "ssl_certificate" in block):
            continue
        for line in re.findall(r"\bserver_name\s+([^;]+);", block):
            for name in line.split():
                name = name.lower().strip(".")
                if DOMAIN_RE.match(name):
                    names.add(name)
    return sorted(names)


def ssl_report(now=None):
    now = now or time.time()
    certs = []
    for pattern in CERT_GLOBS:
        for path in sorted(glob.glob(pattern)):
            if os.path.basename(path) in ACME_SKIP or BACKUP_RE.search(os.path.basename(os.path.dirname(path))):
                continue
            c = read_cert(path, now)
            if c:
                certs.append(c)
    renew = renew_status()
    domains = nginx_domains(run_text(["nginx", "-T"], timeout=15))
    nodes = node_certs(now)
    if not certs and not renew["certbot_installed"] and not domains and not nodes:
        return None
    out = {"certs": certs, "renew": renew, "domains": domains}
    if nodes:
        out["node_certs"] = nodes
    return out


def parse_cert_ips(text):
    return re.findall(r"IP Address:([0-9A-Fa-f.:]+)", text)


def node_certs(now):
    """PasarGuard node certificates: name of the node directory, expiry and the IPs they were issued for."""
    out = []
    for pattern in NODE_CERT_GLOBS:
        for path in sorted(glob.glob(pattern))[:50]:
            name = os.path.basename(os.path.dirname(os.path.dirname(path)))
            if BACKUP_RE.search(name):
                continue
            text = run_text(["openssl", "x509", "-noout", "-enddate", "-ext", "subjectAltName", "-in", path], timeout=5)
            end = parse_cert_end(text)
            if end is None:
                continue
            out.append({"name": clean_text(name, 64), "source": "pasarguard-node", "not_after": end,
                        "days_left": int((end - now) // 86400), "ips": parse_cert_ips(text)[:20],
                        "domains": parse_cert_names(text)[:20]})
    return out


def ssl_cached(state):
    at, value = state.get("ssl") or (0, None)
    if time.time() - at > SSL_TTL_S:
        try:
            value = ssl_report()
        except Exception as e:  # a broken cert file must never stop the report
            log("ssl scan failed: %s" % e)
        state["ssl"] = (time.time(), value)
    return value


# ---- read-only checks (0.3.0): what the server listens on, runs and is configured with ----
#
# Every collector only reads: files under /proc, /sys and /etc, and list/show commands with short timeouts.
# Each runs in its own thread at its own cadence; the report waits for them at most CHECKS_BUDGET_S, takes the
# last good value of a collector that is still busy, and names a failed one in checks_error. Reports carry
# names, states and counts only: never config values, tokens, environment, or log lines.

CHECKS_BUDGET_S = 4.0
CMD_TIMEOUT_S = 5
SLOW_TIMEOUT_S = 8  # docker and journal
STUCK_S = 120  # a collector thread older than this is given up and may be started again
LIST_MAX = 300
STR_MAX = 200
UNIT_PATTERN = re.compile(r"^(backpack-|relay-dnat|backhaul|gre-|wattun@|dl-|xray|x-ui|pasarguard|panel-dnat|mobin-dnat|nginx|fail2ban)")
# listeners on ephemeral ports are kept only for processes like these
KEEP_PROC_RE = re.compile(r"xray|backhaul|backpack|wattun|rathole|frp|gost|nginx|sshd|haproxy|sing-box|hysteria|tunnel|"
                          r"pasarguard|dagger|paqet|realm|x-ui", re.I)
SAFE_TEXT_RE = re.compile(r"[^A-Za-z0-9@._:/+=,()\[\] -]")
# credentials in URLs, key=value secrets and long token-like runs never leave the server
SECRET_RES = (
    re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/@]*@\S*"),
    re.compile(r"(?i)\b[\w.-]*(token|secret|passw(or)?d|passwd|api[_-]?key|private[_-]?key|auth)[\w.-]*\s*[=:]\s*\S+"),
    re.compile(r"[A-Za-z0-9+/_=-]{32,}"),
)


def clean_text(value, limit=STR_MAX, scrub=False):
    """A short printable string, or None; with scrub, anything that looks like a secret is removed first."""
    if value is None:
        return None
    text = str(value)
    for rx in SECRET_RES if scrub else ():
        text = rx.sub("[redacted]", text)
    text = SAFE_TEXT_RE.sub("", text).strip()
    return text[:limit] or None


def bounded(value, depth=0):
    """The value with every list cut to LIST_MAX items and every string to STR_MAX characters."""
    if depth > 8:
        return None
    if isinstance(value, str):
        return value[:STR_MAX]
    if isinstance(value, (list, tuple)):
        return [bounded(v, depth + 1) for v in list(value)[:LIST_MAX]]
    if isinstance(value, dict):
        return {str(k)[:64]: bounded(v, depth + 1) for k, v in list(value.items())[:LIST_MAX]}
    return value


def has(binary):
    return shutil.which(binary) is not None


def run_check(argv, timeout=CMD_TIMEOUT_S, ok=(0,), input=None):
    """(exit code, stdout) of a read-only command; raises when it is missing, times out or fails."""
    r = subprocess.run(argv, input=input, capture_output=True, text=True, timeout=timeout, errors="replace",
                       stdin=None if input is not None else subprocess.DEVNULL)
    if r.returncode not in ok:
        raise RuntimeError("%s exited %d" % (os.path.basename(argv[0]), r.returncode))
    return r.returncode, r.stdout


def check_out(argv, timeout=CMD_TIMEOUT_S, ok=(0,)):
    return run_check(argv, timeout, ok)[1]


def stream_lines(argv, on_line, timeout, max_bytes=16 << 20, merge_stderr=False):
    """Feeds each output line (bytes) to on_line without holding the output; returns the exit code.

    Stops reading after max_bytes; raises TimeoutExpired when the command outlives the timeout."""
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT if merge_stderr else subprocess.DEVNULL)
    killed = []

    def kill():
        killed.append(True)
        proc.kill()

    timer = threading.Timer(timeout, kill)
    timer.start()
    seen = 0
    try:
        for raw in proc.stdout:
            seen += len(raw)
            on_line(raw)
            if seen > max_bytes:
                break
    finally:
        timer.cancel()
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()
        code = proc.wait()
    if killed:
        raise subprocess.TimeoutExpired(argv, timeout)
    return code if seen <= max_bytes else 0


def count_lines(argv, needles, timeout, merge_stderr=False):
    counts = [0] * len(needles)

    def on_line(raw):
        for i, needle in enumerate(needles):
            if needle in raw:
                counts[i] += 1
    code = stream_lines(argv, on_line, timeout, merge_stderr=merge_stderr)
    return counts, code


def read_int(path):
    try:
        return int(read(path).split()[0])
    except (ValueError, IndexError):
        return None


def read_word(path, limit=64):
    text = read(path).strip()
    return clean_text(text, limit) if text else None


def soft(fn, *args):
    """fn(*args), or None when it fails: one missing tool must not blank a whole collector."""
    try:
        return fn(*args)
    except Exception:
        return None


# -- listeners: ss -H -tulnp --

SS_PROC_RE = re.compile(r'users:\(\("([^"]{1,64})"')


UDP_COLLAPSE_OVER = 12


def parse_ss_listeners(text):
    seen, out = set(), []
    for line in text.splitlines():
        f = line.split()
        if len(f) < 5 or f[0] not in ("tcp", "udp"):
            continue
        port = f[4].rsplit(":", 1)[-1]
        if not port.isdigit():
            continue
        port = int(port)
        m = SS_PROC_RE.search(line)
        proc = clean_text(m.group(1), 40) if m else None
        if port == 0 or (port > 32768 and not (proc and KEEP_PROC_RE.search(proc))):
            continue
        key = (f[0], port, proc)
        if key not in seen:
            seen.add(key)
            out.append({"proto": f[0], "port": port, "proc": proc})
    # a process holding many UDP sockets (xray keeps one per client flow) is one summary row, not a list
    udp_by_proc = {}
    for x in out:
        if x["proto"] == "udp":
            udp_by_proc.setdefault(x["proc"], []).append(x)
    crowded = {proc for proc, rows in udp_by_proc.items() if len(rows) > UDP_COLLAPSE_OVER}
    out = [x for x in out if not (x["proto"] == "udp" and x["proc"] in crowded)]
    out += [{"proto": "udp", "port": 0, "proc": proc, "count": len(udp_by_proc[proc])} for proc in sorted(crowded, key=str)]
    out.sort(key=lambda x: (x["port"], x["proto"], x["proc"] or ""))
    return out[:LIST_MAX]


def collect_listeners(memo):
    if not has("ss"):
        return None
    return parse_ss_listeners(check_out(["ss", "-H", "-tulnp"]))


# -- units: enabled tunnel/panel/firewall units and anything in auto-restart --

def parse_unit_files(text):
    """Enabled unit names from `systemctl list-unit-files --state=enabled --no-legend --plain`."""
    out = []
    for line in text.splitlines():
        f = line.split()
        if len(f) >= 2 and f[1].startswith("enabled") and "@." not in f[0]:
            out.append(f[0])
    return out


def parse_list_units(text):
    """(name, active, sub) from `systemctl list-units --all --no-legend --plain`."""
    out = []
    for line in text.splitlines():
        f = line.split()
        if f and f[0] in ("●", "×", "*"):
            f = f[1:]
        if len(f) >= 4:
            out.append((f[0], f[2], f[3]))
    return out


def parse_systemctl_show(text):
    """One dict per unit from `systemctl show -p ...` with several units (blocks split by a blank line)."""
    blocks, cur = [], {}
    for line in text.splitlines() + [""]:
        if not line.strip():
            if cur:
                blocks.append(cur)
            cur = {}
            continue
        k, _, v = line.partition("=")
        cur[k.strip()] = v.strip()
    return blocks


def collect_units(memo):
    if not has("systemctl"):
        return None
    enabled = [n for n in parse_unit_files(check_out(["systemctl", "list-unit-files", "--state=enabled",
                                                      "--no-legend", "--plain"])) if UNIT_PATTERN.match(n)]
    loaded = parse_list_units(check_out(["systemctl", "list-units", "--all", "--no-legend", "--plain"]))
    names = list(dict.fromkeys(enabled + [n for n, _, sub in loaded if UNIT_PATTERN.match(n) or sub == "auto-restart"]))
    names = [n for n in names if UNIT_RE.match(n)][:LIST_MAX]
    if not names:
        return []
    out = []
    for b in parse_systemctl_show(check_out(["systemctl", "show", "-p", "Id,ActiveState,SubState,NRestarts,UnitFileState",
                                             "--"] + names)):
        is_enabled = b.get("UnitFileState", "").startswith("enabled")
        if not (is_enabled or b.get("SubState") == "auto-restart"):
            continue
        restarts = b.get("NRestarts", "")
        out.append({"name": clean_text(b.get("Id"), 100), "enabled": is_enabled, "active": clean_text(b.get("ActiveState"), 20),
                    "sub": clean_text(b.get("SubState"), 20), "restarts": int(restarts) if restarts.isdigit() else None})
    return out


# -- containers: docker ps -a + docker inspect (selected fields only, never env or command) --

PS_FORMAT = "{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.State}}\t{{.Status}}"
_INSPECT_HEAD = '{"id":{{json .Id}},"restarts":{{json .RestartCount}},"policy":{{json .HostConfig.RestartPolicy.Name}},'
_INSPECT_TAIL = ('"status":{{json .State.Status}},"exit_code":{{json .State.ExitCode}},"oom":{{json .State.OOMKilled}},'
                 '"started":{{json .State.StartedAt}},"image":{{json .Config.Image}}}')
# New Docker answers a missing .State.Health with an error, older Docker with an empty value: try both, then go without
INSPECT_FORMATS = (
    _INSPECT_HEAD + '"health":{{with index .State "Health"}}{{json .Status}}{{else}}null{{end}},' + _INSPECT_TAIL,
    _INSPECT_HEAD + '"health":{{if .State.Health}}{{json .State.Health.Status}}{{else}}null{{end}},' + _INSPECT_TAIL,
    _INSPECT_HEAD + '"health":null,' + _INSPECT_TAIL,
)
INSPECT_FORMAT = INSPECT_FORMATS[0]
DB_IMAGE_RE = re.compile(r"mysql|mariadb|postgres|timescale|redis|pgbouncer|adminer|phpmyadmin", re.I)
NODE_IMAGE_RE = re.compile(r"(^|/)node(:|@|$)")
CONTAINER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def image_tag(image):
    """repo:tag without a digest."""
    return clean_text(str(image or "").split("@")[0], 100)


def parse_docker_ps(text):
    out = []
    for line in text.splitlines():
        f = line.split("\t")
        if len(f) >= 5 and CONTAINER_RE.match(f[1].split(",")[0]):
            out.append({"id": f[0][:64], "name": f[1].split(",")[0], "image": f[2], "state": f[3], "status": f[4]})
    return out


def parse_docker_time(value):
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)", str(value or ""))
    if not m or m.group(1) == "0001":
        return None
    return calendar.timegm(tuple(int(x) for x in m.groups()) + (0, 0, 0))


def parse_docker_inspect(text):
    out = {}
    for line in text.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if isinstance(d, dict) and isinstance(d.get("id"), str):
            out[d["id"]] = d
    return out


def collect_containers(memo):
    if not has("docker"):
        return None
    rows = parse_docker_ps(check_out(["docker", "ps", "-a", "--no-trunc", "--format", PS_FORMAT], timeout=SLOW_TIMEOUT_S))[:50]
    details = {}
    if rows:
        error = None
        for fmt in INSPECT_FORMATS:
            try:
                details = parse_docker_inspect(check_out(["docker", "inspect", "--format", fmt] + [r["id"] for r in rows],
                                                         timeout=SLOW_TIMEOUT_S))
                break
            except Exception as e:  # noqa: BLE001 - the next format may work on this Docker
                error = e
        else:
            raise error
    out = []
    for r in rows:
        d = details.get(r["id"], {})
        num = lambda v: v if isinstance(v, int) and not isinstance(v, bool) else None  # noqa: E731
        out.append({"name": r["name"], "image": image_tag(d.get("image") or r["image"]), "state": clean_text(r["state"], 20),
                    "status": clean_text(r["status"], 60, scrub=True), "restarts": num(d.get("restarts")),
                    "health": clean_text(d.get("health"), 20), "policy": clean_text(d.get("policy"), 20),
                    "exit_code": num(d.get("exit_code")), "oom_killed": d.get("oom") if isinstance(d.get("oom"), bool) else None,
                    "started_at": parse_docker_time(d.get("started"))})
    return out


def pasarguard_containers(rows):
    """Running PasarGuard panel and node containers (database containers of the same project excluded)."""
    return [r for r in rows if "pasarguard" in (r["name"] + " " + r["image"]).lower() and not DB_IMAGE_RE.search(r["image"])
            and r["state"] == "running"]


LOG_SIGNATURES = (("unavailable", b"Code: Unavailable"), ("keepalive", b"keep alive timeout"),
                  ("queuepool", b"QueuePool limit"), ("certfail", b"CERTIFICATE_VERIFY_FAILED"))


def collect_container_logs(memo):
    """Per PasarGuard container, how many log lines of the last 10 minutes match each known failure. Counts only."""
    if not has("docker"):
        return None
    rows = pasarguard_containers(parse_docker_ps(check_out(["docker", "ps", "--no-trunc", "--format", PS_FORMAT],
                                                           timeout=SLOW_TIMEOUT_S)))
    if not rows:
        return None
    out, until = [], time.monotonic() + 30
    for r in rows[:20]:
        if time.monotonic() > until:
            break
        counts, _ = count_lines(["docker", "logs", "--since", "10m", r["name"]], [s for _, s in LOG_SIGNATURES],
                                SLOW_TIMEOUT_S, merge_stderr=True)
        out.append(dict({"container": r["name"]}, **{k: n for (k, _), n in zip(LOG_SIGNATURES, counts)}))
    return out


# -- nftables: table names, the relay DNAT table, number of DNAT rules --

def parse_nft_tables(text):
    out = []
    for line in text.splitlines():
        f = line.split()
        if len(f) == 3 and f[0] == "table":
            out.append("%s %s" % (f[1], clean_text(f[2], 64)))
    return out


def nft_dnat_counter():
    by_table, cur = {}, [None]

    def on_line(raw):
        line = raw.decode("utf-8", "replace").strip()
        if line.startswith("table "):
            f = line.split()
            cur[0] = clean_text(f[2], 64) if len(f) >= 3 else None
        elif "dnat to" in line and cur[0]:
            by_table[cur[0]] = by_table.get(cur[0], 0) + 1
    return by_table, on_line


def collect_nft(memo):
    if not has("nft"):
        return None
    tables = parse_nft_tables(check_out(["nft", "list", "tables"]))
    by_table, on_line = nft_dnat_counter()
    if stream_lines(["nft", "list", "ruleset"], on_line, CMD_TIMEOUT_S) != 0:
        raise RuntimeError("nft list ruleset failed")
    return {"tables": tables[:LIST_MAX], "relay_dnat": any(t.split()[-1] == "relay_dnat" for t in tables),
            "dnat_rules": sum(by_table.values()), "dnat_by_table": dict(list(by_table.items())[:50]),
            "ip_forward": read_int("/proc/sys/net/ipv4/ip_forward")}


# -- conntrack: live limits and drop counters --

def parse_nf_conntrack_stat(text):
    """Sums of the per-CPU hex counters in /proc/net/stat/nf_conntrack."""
    lines = [line.split() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    head, sums = lines[0], {}
    for row in lines[1:]:
        for k, v in zip(head, row):
            try:
                sums[k] = sums.get(k, 0) + int(v, 16)
            except ValueError:
                pass
    return sums


def collect_conntrack(memo):
    base = "/proc/sys/net/netfilter/"
    count = read_int(base + "nf_conntrack_count")
    if count is None:
        return {"module_loaded": os.path.isdir("/sys/module/nf_conntrack"), "count": None, "max": None,
                "tcp_established_timeout": None, "insert_failed": None, "drop": None, "early_drop": None}
    stat = parse_nf_conntrack_stat(read("/proc/net/stat/nf_conntrack")) or {}
    return {"module_loaded": True, "count": count, "max": read_int(base + "nf_conntrack_max"),
            "tcp_established_timeout": read_int(base + "nf_conntrack_tcp_timeout_established"),
            "insert_failed": stat.get("insert_failed"), "drop": stat.get("drop"), "early_drop": stat.get("early_drop")}


# -- kernel and host baseline --

def parse_vmstat(text, key):
    m = re.search(r"(?m)^%s\s+(\d+)$" % re.escape(key), text)
    return int(m.group(1)) if m else None


def parse_timedatectl(text):
    value = text.strip().rpartition("=")[2].strip().lower()
    return {"yes": True, "no": False}.get(value)


SIZE_UNITS = {"B": 1 / 1048576, "K": 1 / 1024, "M": 1, "G": 1024, "T": 1048576}


def parse_journal_usage(text):
    """MB from `journalctl --disk-usage` ("... take up 1.2G in the file system.")."""
    m = re.search(r"take up ([\d.]+)\s*([BKMGT])", text)
    return round(float(m.group(1)) * SIZE_UNITS[m.group(2)], 1) if m else None


def inode_pct(path="/"):
    st = os.statvfs(path)
    return round(100.0 * (st.f_files - st.f_ffree) / st.f_files, 1) if st.f_files else None


def collect_kernel(memo):
    p = "/proc/sys/"
    return {
        "congestion": read_word(p + "net/ipv4/tcp_congestion_control"),
        "qdisc": read_word(p + "net/core/default_qdisc"),
        "mtu_probing": read_int(p + "net/ipv4/tcp_mtu_probing"),
        "ip_forward": read_int(p + "net/ipv4/ip_forward"),
        "reserved_ports": read(p + "net/ipv4/ip_local_reserved_ports").strip()[:STR_MAX] or None,
        "swappiness": read_int(p + "vm/swappiness"),
        "oom_kill": parse_vmstat(read("/proc/vmstat"), "oom_kill"),
        "boot_id": read_word(p + "kernel/random/boot_id"),
        "ntp_synced": soft(lambda: parse_timedatectl(check_out(["timedatectl", "show", "-p", "NTPSynchronized"])))
        if has("timedatectl") else None,
        "inode_pct": soft(inode_pct),
        "journal_mb": soft(lambda: parse_journal_usage(check_out(["journalctl", "--disk-usage"], timeout=SLOW_TIMEOUT_S)))
        if has("journalctl") else None,
    }


# -- security: firewall, fail2ban, sshd --

def parse_ufw_conf(text):
    m = re.search(r"(?m)^\s*ENABLED\s*=\s*(\w+)", text)
    return None if not m else ("active" if m.group(1).lower() == "yes" else "inactive")


def parse_sshd_password_auth(text):
    m = re.search(r"(?m)^passwordauthentication\s+(\w+)", text)
    return None if not m else m.group(1).lower() == "yes"


def fail2ban_state():
    b = parse_systemctl_show(check_out(["systemctl", "show", "-p", "LoadState,ActiveState", "fail2ban.service"]))
    if not b or b[0].get("LoadState") != "loaded":
        return None
    return clean_text(b[0].get("ActiveState"), 20)


def collect_security(memo):
    conf = read("/etc/ufw/ufw.conf")
    return {
        "ufw": parse_ufw_conf(conf) if conf else None,
        "fail2ban": soft(fail2ban_state) if has("systemctl") else None,
        "password_auth": soft(lambda: parse_sshd_password_auth(check_out(["sshd", "-T"]))) if has("sshd") else None,
    }


# -- apt: what would make the next reboot or upgrade fail --

def collect_apt(memo):
    if not has("dpkg"):
        return None
    audit = check_out(["dpkg", "--audit"], ok=(0, 1))
    holds = soft(lambda: check_out(["apt-mark", "showhold"]).split()) if has("apt-mark") else None
    pkgs = {line.strip() for line in read("/var/run/reboot-required.pkgs").splitlines() if line.strip()}
    return {"dpkg_audit": len([line for line in audit.splitlines() if line.strip()]),
            "held_docker": None if holds is None else any(p in holds for p in HOLD_PKGS),
            "reboot_required_pkgs": len(pkgs)}


# -- tunnels: ports, peer and interface from tunnel configs; every other key (token, secret, ...) is dropped --

TUNNEL_GLOBS = (("backhaul", "/etc/backhaul/*.toml"), ("backpack", "/etc/backpack/*.toml"), ("rathole", "/etc/rathole/*.toml"),
                ("frp", "/etc/frp/*.toml"), ("frp", "/etc/frp/*.ini"), ("wattun", "/etc/wattun/*.yml"),
                ("wattun", "/etc/wattun/*.yaml"))
# the only keys read from a tunnel config
PEER_KEYS = ("remote_addr", "server_addr", "serveraddr", "peer_ip", "peer", "remote")
LISTEN_KEYS = ("bind_addr", "bindaddr", "bind_port", "bindport", "listen", "listen_port", "remote_port", "remoteport")
IFACE_KEYS = ("iface", "interface", "tun_name", "device", "dev", "ifname")
MODE_KEYS = ("mode", "role")
KIND_KEYS = ("transport", "carrier", "type")
HOST_RE = re.compile(r"^[A-Za-z0-9.:\[\]_-]{1,100}$")
IFACE_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,15}$")
WORD_RE = re.compile(r"^[A-Za-z0-9_-]{1,24}$")
TUNNEL_NAME_RE = re.compile(r"^[A-Za-z0-9@._-]{1,64}$")
LINK_KINDS = {768: "ipip", 776: "sit", 778: "gre", 823: "ip6gre", 65534: "tun"}
SYS_NET = "/sys/class/net"


def strip_comment(line):
    out, quote = [], None
    for ch in line:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "#;":
            break
        out.append(ch)
    return "".join(out).strip()


def config_items(text):
    """(section, key, raw value) from TOML, INI or simple YAML; arrays may span lines."""
    section, pending = "", None
    for line in text.splitlines():
        line = strip_comment(line)
        if not line:
            continue
        if pending is not None:
            pending[2] += " " + line
            if pending[2].count("[") <= pending[2].count("]"):
                yield tuple(pending)
                pending = None
            continue
        if line.startswith("["):
            section = line.strip("[] ").lower()
            continue
        m = re.match(r"^-?\s*([A-Za-z0-9_.-]+)\s*[=:]\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1).lower().rsplit(".", 1)[-1], m.group(2).strip()
        if value.startswith("[") and value.count("[") > value.count("]"):
            pending = [section, key, value]
            continue
        yield section, key, value


def scalar(value):
    m = re.match(r"""^["']([^"']*)["']""", value)
    return m.group(1) if m else value.split()[0] if value.split() else ""


def port_of(text):
    """The port of "443", ":443", "0.0.0.0:443" or "[::]:443"."""
    tail = str(text).strip().rsplit(":", 1)[-1]
    return int(tail) if tail.isdigit() and 0 < int(tail) < 65536 else None


def map_ports(value):
    """Listening ports of a Backhaul/BackPack `ports = ["443", "8443=127.0.0.1:8443", "2000-2010=..."]` list."""
    out = []
    for item in re.findall(r"""["']([^"']*)["']|(\d+)""", value):
        item = item[0] or item[1]
        left = item.split("=", 1)[0].strip()
        rng = re.fullmatch(r"(?:.*:)?(\d+)-(\d+)", left)
        if rng:
            lo, hi = int(rng.group(1)), int(rng.group(2))
            if 0 < lo <= hi < 65536:
                out.extend(range(lo, min(hi, lo + LIST_MAX) + 1))
            continue
        p = port_of(left)
        if p:
            out.append(p)
    return out


def parse_tunnel_config(kind, name, text):
    """{name, type, mode, transport, ports, peer, iface} of one tunnel config; nothing else is kept."""
    info = {"name": name, "type": kind, "mode": None, "transport": None, "ports": [], "peer": None, "iface": None}
    for section, key, value in config_items(text):
        head = section.split(".")[0]
        if info["mode"] is None and head in ("server", "client", "common"):
            info["mode"] = head if head != "common" else None
        if key == "ports":
            info["ports"].extend(map_ports(value))
        elif key in LISTEN_KEYS:
            p = port_of(scalar(value))
            if p and head != "client":
                info["ports"].append(p)
        elif key in PEER_KEYS and info["peer"] is None:
            v = scalar(value)
            info["peer"] = v if HOST_RE.match(v) else None
        elif key in IFACE_KEYS and info["iface"] is None:
            v = scalar(value)
            info["iface"] = v if IFACE_RE.match(v) else None
        elif key in MODE_KEYS:
            v = scalar(value).lower()
            info["mode"] = v if WORD_RE.match(v) else info["mode"]
        elif key in KIND_KEYS and info["transport"] is None:
            v = scalar(value).lower()
            info["transport"] = v if WORD_RE.match(v) else None
    info["ports"] = sorted(set(info["ports"]))[:LIST_MAX]
    if info["mode"] is None and kind == "frp":
        info["mode"] = "server" if name.startswith("frps") else "client" if name.startswith("frpc") else None
    return info


def unit_candidates(kind, name):
    return {
        "backhaul": ["backhaul-%s.service" % name, "backhaul.service"],
        "backpack": ["backpack-%s.service" % name],
        "rathole": ["rathole@%s.service" % name, "ratholes@%s.service" % name, "ratholec@%s.service" % name,
                    "rathole-%s.service" % name],
        "frp": ["%s.service" % name, "frps@%s.service" % name, "frpc@%s.service" % name],
        "wattun": ["wattun@%s.service" % name],
    }[kind]


def iface_bytes(iface):
    base = "%s/%s/statistics/" % (SYS_NET, iface)
    rx, tx = read_int(base + "rx_bytes"), read_int(base + "tx_bytes")
    return (rx, tx) if rx is not None and tx is not None else None


def tunnel_links():
    """L3 tunnel interfaces (GRE, SIT, IPIP, TUN/WireGuard) with their byte counters."""
    out = []
    for path in sorted(glob.glob(SYS_NET + "/*"))[:LIST_MAX * 2]:
        iface = os.path.basename(path)
        kind = LINK_KINDS.get(read_int(path + "/type"))
        if not kind or not IFACE_RE.match(iface):
            continue
        b = iface_bytes(iface)
        out.append({"iface": iface, "kind": kind, "mtu": read_int(path + "/mtu"), "state": read_word(path + "/operstate", 12),
                    "rx_bytes": b[0] if b else None, "tx_bytes": b[1] if b else None})
    return out[:LIST_MAX]


def collect_tunnels(memo):
    found = []
    for kind, pattern in TUNNEL_GLOBS:
        for path in sorted(glob.glob(pattern))[:100]:
            name = os.path.splitext(os.path.basename(path))[0]
            if not TUNNEL_NAME_RE.match(name) or BACKUP_RE.search(name):
                continue
            found.append(parse_tunnel_config(kind, name, read(path)[:1 << 20]))
    links = tunnel_links()
    if not found and not links:
        return None
    states = {}
    if found and has("systemctl"):
        names = [u for t in found for u in unit_candidates(t["type"], t["name"]) if UNIT_RE.match(u)]
        blocks = soft(lambda: parse_systemctl_show(check_out(["systemctl", "show", "-p", "Id,LoadState,ActiveState", "--"]
                                                            + list(dict.fromkeys(names))[:LIST_MAX]))) or []
        states = {b.get("Id"): b.get("ActiveState") for b in blocks if b.get("LoadState") == "loaded"}
    for t in found:
        unit = next((u for u in unit_candidates(t["type"], t["name"]) if u in states), None)
        t["unit"], t["active"] = unit, states.get(unit) if unit else None
        if t["iface"]:
            b = iface_bytes(t["iface"])
            t["rx_bytes"], t["tx_bytes"] = (b[0], b[1]) if b else (None, None)
    return {"configs": found[:LIST_MAX], "links": links}


# -- PasarGuard panel: one fixed read-only script inside the panel's own container --

# Runs as `docker exec -i -w /code CONTAINER python -`. It reads the panel's own database settings inside the
# container, makes every session read-only with a short statement timeout, uses windowed queries on indexed
# columns, and prints one JSON object of names, states and numbers. It never prints the database address or
# an exception message, only exception class names.
PANEL_SCRIPT = r'''
import asyncio, datetime, json, os, signal, sys
signal.alarm(7)
OUT, ERRORS = {}, []


def db_url():
    url = os.environ.get("SQLALCHEMY_DATABASE_URL")
    if not url and os.path.exists("/code/.env"):
        for line in open("/code/.env"):
            k, _, v = line.partition("=")
            if k.strip() == "SQLALCHEMY_DATABASE_URL":
                url = v.strip().strip("'\"")
    return url or "sqlite+aiosqlite:///db.sqlite3"


async def main():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(db_url(), pool_pre_ping=False)
    dialect = engine.dialect.name
    groups = "`groups`" if dialect in ("mysql", "mariadb") else "groups"

    async def read_only(c):
        if dialect == "postgresql":
            await c.execute(text("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY"))
            await c.execute(text("SET statement_timeout = 3000"))
        elif dialect in ("mysql", "mariadb"):
            await c.execute(text("SET SESSION TRANSACTION READ ONLY"))
            try:
                await c.execute(text("SET SESSION max_execution_time = 3000"))
            except Exception:
                await c.execute(text("SET SESSION max_statement_time = 3"))
        elif dialect == "sqlite":
            await c.execute(text("PRAGMA query_only = ON"))
        await c.commit()  # the session settings apply from the next transaction on

    async def fetch(*queries, **params):
        last = None
        for sql in queries:
            try:
                async with engine.connect() as c:
                    await read_only(c)
                    return (await c.execute(text(sql), params)).all()
            except Exception as e:
                last = e
        raise last

    async def part(name, coro):
        try:
            OUT[name] = await coro
        except Exception as e:
            ERRORS.append(name + ":" + type(e).__name__)

    async def nodes():
        rows = await fetch("SELECT id, name, address, port, status, message, keep_alive FROM nodes ORDER BY id LIMIT 300",
                           "SELECT id, name, address, port, status, message, NULL FROM nodes ORDER BY id LIMIT 300")
        return [{"id": r[0], "name": r[1], "address": r[2], "port": r[3], "status": str(r[4] or ""),
                 "message": str(r[5] or "")[:120], "keep_alive": r[6]} for r in rows]

    hour = datetime.datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    async def usage_between(start, end):
        rows = await fetch("SELECT node_id, COUNT(DISTINCT user_id), SUM(used_traffic) FROM node_user_usages "
                           "WHERE created_at >= :a AND created_at < :b GROUP BY node_id", a=start, b=end)
        return [{"node_id": r[0], "users": int(r[1] or 0), "bytes": int(r[2] or 0)} for r in rows]

    async def usage():
        one = datetime.timedelta(hours=1)
        last = await usage_between(hour - one, hour)
        prev = await usage_between(hour - 2 * one, hour - one)
        start = hour - one
        epoch = int((start - datetime.datetime(1970, 1, 1)).total_seconds())
        return {"hour_start": epoch, "last": last, "prev": prev}

    async def admins():
        rows = await fetch("SELECT username, used_traffic, data_limit FROM admins ORDER BY username LIMIT 300",
                           "SELECT username, NULL, NULL FROM admins ORDER BY username LIMIT 300")
        return [{"name": r[0], "used": r[1], "limit": r[2]} for r in rows]

    async def inbounds_without_group():
        rows = await fetch(
            "SELECT i.tag FROM inbounds i WHERE NOT EXISTS (SELECT 1 FROM inbounds_groups_association a JOIN %s g "
            "ON g.id = a.group_id WHERE a.inbound_id = i.id AND NOT g.is_disabled) ORDER BY i.tag LIMIT 300" % groups,
            "SELECT i.tag FROM inbounds i WHERE NOT EXISTS (SELECT 1 FROM inbounds_groups_association a "
            "WHERE a.inbound_id = i.id) ORDER BY i.tag LIMIT 300")
        return [r[0] for r in rows]

    async def user_status():
        rows = await fetch("SELECT status, COUNT(*) FROM users GROUP BY status")
        return {str(r[0]).split(".")[-1].lower(): int(r[1]) for r in rows}

    await part("nodes", nodes())
    await part("usage", usage())
    await part("admins", admins())
    await part("inbounds_without_group", inbounds_without_group())
    await part("user_status", user_status())
    await engine.dispose()


try:
    try:
        OUT["version"] = open("/code/VERSION").read().strip()[:40]
    except OSError:
        OUT["version"] = None
    asyncio.run(main())
    OUT["errors"] = ERRORS
    print(json.dumps(OUT, default=lambda v: int(v) if hasattr(v, "__int__") else None, separators=(",", ":")))
except BaseException as e:
    print(json.dumps({"error": type(e).__name__}))
'''
PANEL_FIND_S = 300
USER_STATUSES = ("active", "limited", "expired", "on_hold", "disabled")
CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,59}$")
PART_ERROR_RE = re.compile(r"^[a-z_]{1,40}:[A-Za-z_][A-Za-z0-9_]{0,59}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9.+_-]{1,40}$")


class PanelError(Exception):
    """A panel read failed; `short` is the only text that reaches the report."""

    def __init__(self, short):
        super().__init__(short)
        self.short = short if CLASS_RE.match(str(short)) else "PanelError"


def find_panel_container():
    """Name of a running PasarGuard panel container (one with /code), or None."""
    if not has("docker"):
        return None
    rows = pasarguard_containers(parse_docker_ps(check_out(["docker", "ps", "--no-trunc", "--format", PS_FORMAT],
                                                           timeout=SLOW_TIMEOUT_S)))
    for r in [r for r in rows if not NODE_IMAGE_RE.search(r["image"])][:5]:
        code, _ = run_check(["docker", "exec", r["name"], "test", "-d", "/code"], ok=(0, 1))
        if code == 0:
            return r["name"]
    return None


def as_int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def clean_panel(d, container):
    """Only known fields of the panel script's answer, each type-checked, capped and scrubbed."""
    if not isinstance(d, dict):
        raise PanelError("BadOutput")
    if "error" in d:
        raise PanelError(d.get("error"))
    rows = lambda v: [x for x in v if isinstance(x, dict)][:LIST_MAX] if isinstance(v, list) else None  # noqa: E731
    nodes = [{"id": as_int(n.get("id")), "name": clean_text(n.get("name"), 64, scrub=True),
              "address": n.get("address") if isinstance(n.get("address"), str) and HOST_RE.match(n["address"]) else None,
              "port": as_int(n.get("port")), "status": clean_text(n.get("status"), 20, scrub=True),
              "message": clean_text(n.get("message"), 120, scrub=True), "keep_alive": as_int(n.get("keep_alive"))}
             for n in rows(d.get("nodes")) or []] if "nodes" in d else None
    usage = None
    if isinstance(d.get("usage"), dict):
        u = d["usage"]
        usage = {"hour_start": as_int(u.get("hour_start"))}
        for k in ("last", "prev"):
            usage[k] = [{"node_id": as_int(x.get("node_id")), "users": as_int(x.get("users")), "bytes": as_int(x.get("bytes"))}
                        for x in rows(u.get(k)) or []]
    admins = [{"name": clean_text(a.get("name"), 64, scrub=True), "used": as_int(a.get("used")), "limit": as_int(a.get("limit"))}
              for a in rows(d.get("admins")) or []] if "admins" in d else None
    tags = d.get("inbounds_without_group")
    tags = [clean_text(t, 64, scrub=True) for t in tags[:LIST_MAX] if isinstance(t, str)] if isinstance(tags, list) else None
    status = None
    if isinstance(d.get("user_status"), dict):
        raw = {str(k): v for k, v in d["user_status"].items() if as_int(v) is not None}
        status = {k: raw.get(k, 0) for k in USER_STATUSES}
        status["other"] = sum(v for k, v in raw.items() if k not in USER_STATUSES)
    version = d.get("version") if isinstance(d.get("version"), str) and VERSION_RE.match(d["version"]) else None
    errors = [e for e in d.get("errors") or [] if isinstance(e, str) and PART_ERROR_RE.match(e)][:20]
    return {"container": container, "version": version, "nodes": nodes, "usage": usage, "admins": admins,
            "inbounds_without_group": tags, "user_status": status, "errors": errors}


def parse_panel_output(text, container):
    lines = [line for line in text.splitlines() if line.strip().startswith("{")]
    try:
        d = json.loads(lines[-1]) if lines else None
    except ValueError:
        raise PanelError("BadOutput")
    return clean_panel(d, container)


def collect_panel(memo):
    now = time.monotonic()
    if now - memo.get("found_at", -1e9) > PANEL_FIND_S:
        memo["container"], memo["found_at"] = find_panel_container(), now
    name = memo.get("container")
    if not name:
        return None
    try:
        _, out = run_check(["docker", "exec", "-i", "-w", "/code", name, "python", "-"], timeout=SLOW_TIMEOUT_S,
                           input=PANEL_SCRIPT)
    except subprocess.TimeoutExpired:
        raise PanelError("Timeout")
    except (OSError, RuntimeError):
        memo["found_at"] = -1e9  # the container may have been replaced: look again next time
        raise PanelError("ExecFailed")
    return parse_panel_output(out, name)


# -- runner: cadence, cache, time budget --

# name, collector, seconds between runs (0 = every report)
COLLECTORS = (
    ("listeners", collect_listeners, 0),
    ("units", collect_units, 0),
    ("conntrack", collect_conntrack, 0),
    ("containers", collect_containers, 60),
    ("nft", collect_nft, 60),
    ("tunnels", collect_tunnels, 60),
    ("kernel", collect_kernel, 300),
    ("security", collect_security, 300),
    ("container_logs", collect_container_logs, 300),
    ("apt", collect_apt, 600),
)
PANEL_COLLECTOR = ("panel", collect_panel, 60)


def all_collectors():
    return COLLECTORS + (PANEL_COLLECTOR,)


def short_error(e):
    if isinstance(e, PanelError):
        return e.short
    if isinstance(e, subprocess.TimeoutExpired):
        return "Timeout"
    return type(e).__name__


def launch(fn, memo):
    job = {"done": threading.Event(), "value": None, "error": None}

    def work():
        try:
            job["value"] = fn(memo)
        except Exception as e:  # a broken collector only blanks its own part
            job["error"] = short_error(e)
        finally:
            job["done"].set()
    threading.Thread(target=work, name="dl-check", daemon=True).start()
    return job


def start_checks(state, clock=time.monotonic):
    """Starts every collector that is due and not still running; returns at once."""
    ck = state.setdefault("checks", {})
    now = clock()
    for name, fn, every in all_collectors():
        s = ck.setdefault(name, {"next": 0.0, "value": None, "error": None, "at": None, "job": None, "memo": {}})
        if s["job"] is not None and now - s["started"] > STUCK_S:
            s["job"], s["error"], s["next"] = None, "Timeout", now + every
        if s["job"] is None and now >= s["next"]:
            s["job"], s["started"] = launch(fn, s["memo"]), now
    return now


def finish_checks(state, deadline, clock=time.monotonic):
    """Waits for running collectors until the deadline; returns (checks, checks_error, panel, panel_error)."""
    ck = state.get("checks") or {}
    for s in ck.values():
        if s["job"] is not None:
            s["job"]["done"].wait(max(0.0, deadline - clock()))
    now = clock()
    out, errors, panel, panel_error = {}, [], None, None
    for name, fn, every in all_collectors():
        s = ck.get(name)
        if s is None:
            value, err = None, None
        else:
            job = s["job"]
            if job is not None and job["done"].is_set():
                s["job"], s["next"] = None, now + every
                s["value"], s["error"], s["at"] = job["value"], job["error"], None if job["error"] else now
            value, err = s["value"], s["error"]
            if s["job"] is not None and (s["at"] is None or now - s["at"] > max(3 * every, 90)):
                value, err = None, "Timeout"  # still running and nothing recent to show
            if err:
                value = None
        if name == "panel":
            panel, panel_error = value, err
            continue
        out[name] = bounded(value)
        if err:
            errors.append(name)
    if isinstance(out.get("security"), dict):
        listeners = out.get("listeners")
        out["security"]["sshd_ports"] = sorted({x["port"] for x in listeners if x["proto"] == "tcp" and x["proc"] == "sshd"}) \
            if isinstance(listeners, list) else None
    return out, errors, bounded(panel), panel_error


def checks_fields(state, started):
    checks, errors, panel, panel_error = finish_checks(state, started + CHECKS_BUDGET_S)
    out = {"checks": checks, "checks_error": errors}
    if panel is not None:
        out["panel"] = panel
    if panel_error:
        out["panel_error"] = panel_error
    return out


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


def certbot_job(verb, args, state):
    name = args.get("name")
    if not isinstance(name, str) or not CERT_NAME_RE.match(name):
        raise ValueError("bad certificate name")
    r = subprocess.run(["certbot", verb, "--cert-name", name, "--non-interactive"],
                       capture_output=True, text=True, timeout=300)
    state["ssl"] = (0, None)  # rescan on the next report so the change shows at once
    tail = (r.stdout + r.stderr).strip()[-400:]
    if r.returncode != 0:
        raise RuntimeError(tail or "certbot failed")
    return {"name": name, "output": tail}


def job_cert_renew(args, state):
    return certbot_job("renew", args, state)


def job_cert_delete(args, state):
    return certbot_job("delete", args, state)


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


# ---- diagnostics and service actions: each returns {"output": text} for the panel to show ----

OUTPUT_MAX = 6000
UNIT_RE = re.compile(r"^[A-Za-z0-9@._:-]{1,100}$")


def run_cmd(argv, timeout=25):
    """Runs a command and returns its output (stdout then stderr), cut to what a report may carry."""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, errors="replace")
    except FileNotFoundError:
        raise RuntimeError("%s is not installed on this server" % argv[0])
    except subprocess.TimeoutExpired:
        raise RuntimeError("%s took longer than %d seconds" % (argv[0], timeout))
    text = (r.stdout + r.stderr).strip()
    return text, r.returncode


def output_of(text):
    text = text.strip()
    if len(text) > OUTPUT_MAX:
        text = text[:OUTPUT_MAX] + "\n… (cut)"
    return {"output": text or "(empty)"}


def unit_arg(args, required=False):
    unit = args.get("unit")
    if unit in (None, ""):
        if required:
            raise ValueError("args.unit is required")
        return None
    if not isinstance(unit, str) or not UNIT_RE.match(unit):
        raise ValueError("invalid unit name")
    return unit


def job_processes(args, state):
    text, _ = run_cmd(["ps", "-eo", "pid,user:12,pcpu,pmem,etime,args", "--sort=-pcpu", "--width", "160"])
    return output_of("\n".join(text.splitlines()[:16]))


def job_ports(args, state):
    text, _ = run_cmd(["ss", "-H", "-tulpn"])
    lines = text.splitlines()
    return output_of("\n".join(lines[:80]) + ("\n… %d more" % (len(lines) - 80) if len(lines) > 80 else ""))


def job_disk_usage(args, state):
    df, _ = run_cmd(["df", "-h", "-x", "tmpfs", "-x", "devtmpfs", "-x", "squashfs", "-x", "overlay"])
    du, _ = run_cmd(["sh", "-c", "du -xh --max-depth=1 /var /home /root /opt 2>/dev/null | sort -rh | head -14"], timeout=28)
    return output_of(df + "\n\n" + du)


def job_journal(args, state):
    n = args.get("lines", 100)
    if not isinstance(n, int) or not 10 <= n <= 300:
        raise ValueError("args.lines must be 10 to 300")
    argv = ["journalctl", "--no-pager", "-o", "short-iso", "-n", str(n)]
    unit = unit_arg(args)
    if unit:
        argv += ["-u", unit]
    text, _ = run_cmd(argv)
    return output_of(text[-OUTPUT_MAX:])


def job_traceroute(args, state):
    target = args.get("target")
    if not valid_host(target):
        raise ValueError("invalid target")
    for argv in (["mtr", "-rwn", "-c", "4", target], ["traceroute", "-n", "-w", "1", "-q", "1", "-m", "20", target],
                 ["tracepath", "-n", "-m", "20", target]):
        if shutil.which(argv[0]):
            text, _ = run_cmd(argv, timeout=40)
            return output_of(text)
    raise RuntimeError("none of mtr, traceroute or tracepath is installed")


def job_http_check(args, state):
    url = http_url(args.get("url"))
    start = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            code, got = r.status, len(r.read(1 << 20))
    except urllib.error.HTTPError as e:
        code, got = e.code, 0
    took = time.monotonic() - start
    return {"output": "HTTP %s - %.2f s - %d bytes read" % (code, took, got), "status": code}


def job_dns_check(args, state):
    host = args.get("target")
    if not valid_host(host):
        raise ValueError("invalid target")
    infos = socket.getaddrinfo(host, None)
    ips = sorted({i[4][0] for i in infos})
    return {"output": "\n".join(ips), "count": len(ips)}


def job_service_restart(args, state):
    unit = unit_arg(args, required=True)
    text, code = run_cmd(["systemctl", "restart", unit], timeout=60)
    active, _ = run_cmd(["systemctl", "is-active", unit])
    if code != 0:
        raise RuntimeError(text[:200] or "restart failed")
    return {"output": "%s: %s" % (unit, active), "active": active == "active"}


def job_vacuum_logs(args, state):
    text, _ = run_cmd(["journalctl", "--vacuum-size=200M"], timeout=60)
    apt, _ = run_cmd(["apt-get", "clean"], timeout=60) if shutil.which("apt-get") else ("", 0)
    return output_of(text + ("\n" + apt if apt else ""))


JOBS = {
    "ping": job_ping,
    "tcp_check": job_tcp_check,
    "speedtest_down": job_speedtest_down,
    "speedtest_up": job_speedtest_up,
    "apt_upgrade_safe": job_apt_upgrade_safe,
    "reboot": job_reboot,
    "cert_renew": job_cert_renew,
    "cert_delete": job_cert_delete,
    "self_update": job_self_update,
    "processes": job_processes,
    "ports": job_ports,
    "disk_usage": job_disk_usage,
    "journal": job_journal,
    "traceroute": job_traceroute,
    "http_check": job_http_check,
    "dns_check": job_dns_check,
    "service_restart": job_service_restart,
    "vacuum_logs": job_vacuum_logs,
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
    state["acct_peers"] = resp.get("acct_peers") or []
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
