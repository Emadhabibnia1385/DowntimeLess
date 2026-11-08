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
import time
import urllib.error
import urllib.parse
import urllib.request

VERSION = "0.2.8"
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
    if not certs and not renew["certbot_installed"] and not domains:
        return None
    return {"certs": certs, "renew": renew, "domains": domains}


def ssl_cached(state):
    at, value = state.get("ssl") or (0, None)
    if time.time() - at > SSL_TTL_S:
        try:
            value = ssl_report()
        except Exception as e:  # a broken cert file must never stop the report
            log("ssl scan failed: %s" % e)
        state["ssl"] = (time.time(), value)
    return value


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
