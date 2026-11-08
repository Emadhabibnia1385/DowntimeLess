"""Fix guides for the AI assistant, one per issue code or failure theme.

Curated by hand from the operator's vpnopsnyx knowledge base (incident numbers and file names are in `source`).
English for the assistant, one Persian line for people. Checks are read-only; every fix needs the owner's yes.
"""
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PRINCIPLES = [
    "Read first, change later: every check below is read-only; any fix needs the owner's explicit yes for that server.",
    "Two agreeing vantage points before calling a host dead or a path filtered (two in-country probes plus one abroad); ICMP alone never decides.",
    "Never leave a location with one relay and never leave a DNS name without an address; add the new record before deleting the old one.",
    "Keep secrets out of output: filter configs with grep -v -i -E 'token|key|secret|pass'; never paste or print tokens, keys or passwords.",
    "Evening peak in Iran is about 19:30-00:30 local (16:00-21:00 UTC); plan risky changes outside it and state both UTC and local time.",
    "A fresh fix is not stable until the next-day re-check; judge paths by real user bytes and data tests, not by unit state or ping.",
]

_FEATURES = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def _issue_sources() -> str:
    """The text of the files that raise issues, so a detector counts as live only when its code is really there."""
    text = ""
    for rel in ("overview/service.py", "overview/detectors.py", "ssl/service.py"):
        try:
            text += (_FEATURES / rel).read_text(encoding="utf-8")
        except OSError:
            pass
    return text


def raised_codes() -> List[str]:
    """Every issue code in the issue-raising source (`ping:<ip>` counts as `ping`)."""
    src = _issue_sources()
    found = set(re.findall(r'(?:_issue|make)\(\s*\w+,\s*"([a-z_]+)', src))
    found |= set(re.findall(r'"code":\s*"([a-z_]+)', src))
    return sorted(found)


def _live(code: str) -> str:
    return "live" if code in raised_codes() else "planned"


def _p(code: str, theme: str, title: str, fa: str, detector: str, causes: List[str], checks: List[str],
       fixes: List[str], never: List[str], source: List[str]) -> Dict[str, Any]:
    return {
        "code": code, "theme": theme, "title": title, "summary_fa": fa, "detector": detector,
        "causes": causes, "checks": checks, "fixes": fixes, "never": never, "source": source,
    }


AUTO = "auto"  # live exactly when the code is raised by the issue source

_ENTRIES: List[Dict[str, Any]] = [
    # ---- codes raised today ----
    _p("offline", "host", "Server stopped reporting",
       "سرور گزارش نمی‌دهد؛ پیش از هر اقدامی از دو مبدأ داخل ایران با پورت‌های داده بسنجید، نه فقط ping.", "live",
       ["Provider traffic quota or billing suspension: unreachable on ALL ports from ALL vantage points, far ends of its tunnels see no bytes (incidents 21, 37, 68)",
        "Provider maintenance, reboot, silent rebuild or resize (incidents 45, 54)",
        "Agent service stopped or crashed while the host itself is fine",
        "Host overloaded (steal, OOM, brute-force load): ping and SSH banner time out while data ports still answer (incident 68)",
        "A filter between the probe and the host: one vantage point is not proof (incidents 8, 40)"],
       ["From two in-country servers in different datacenters: TCP connect to a data port of the host (nc -zv -w 5 HOST PORT); never ping or one SSH banner alone",
        "On the other end of each tunnel: bytes on the tunnel interface and ss -ltn for the forward port",
        "Provider panel: traffic quota, billing, maintenance notices, console",
        "If SSH works: systemctl status downtimeless-agent --no-pager ; uptime -s ; last -x | head",
        "journalctl -u downtimeless-agent --since -1h --no-pager | tail -50 ; find the outage window before declaring anything dead (incident 8)"],
       ["Quota or billing: top up at the provider; tunnel clients that backed off for hours may need a restart to reconnect at once",
        "Agent stopped: systemctl restart downtimeless-agent",
        "A relay confirmed dead: add the other relay to the affected DNS names first, then remove the dead record (never leave a name empty)"],
       ["Do not remove a relay from DNS on one probe or on ping alone: confirm from two independent in-country probes and from the exit side (incident 40)",
        "Never leave a DNS name without an address; resolvers cache NXDOMAIN (incident 35)",
        "Do not reboot or upgrade a second relay while the first one's SSH is unconfirmed (incident 71)"],
       ["incidents.md 8, 21, 35, 37, 40, 58, 68", "capacity.md section 12", "iran-filtering.md section 5"]),

    _p("agent_missing", "host", "Agent not installed or never connected",
       "agent روی این سرور نصب نشده یا هنوز وصل نشده؛ دستور نصب را فقط با اجازهٔ مالک اجرا کنید.", "live",
       ["The install command was never run, or the one-time enroll token was already used",
        "Outbound HTTPS from the server to the panel is blocked or the panel URL is wrong",
        "The agent service crashed at start"],
       ["On the server: systemctl status downtimeless-agent --no-pager",
        "journalctl -u downtimeless-agent -n 30 --no-pager",
        "curl -sS -o /dev/null -w '%{http_code}\\n' https://PANEL_HOST/api/v1/health (expect 200)"],
       ["Create a fresh enroll token in the panel (POST /api/v1/servers/{id}/enroll-token) and run the install command again",
        "Install over an SSH key, never over a pasted root password"],
       ["Never install the agent on a live VPN server without the owner's yes for that server",
        "Do not use a root password pasted in chat; ask for an SSH key and a password change (node-lifecycle section 1)"],
       ["node-lifecycle.md section 1", "ARCHITECTURE.md (agent protocol)"]),

    _p("disk", "host", "Disk filling up",
       "دیسک رو به پر شدن است؛ لاگ‌ها و بکاپ‌های قدیمی را بررسی کنید و بدون تأیید چیزی پاک نکنید.", "live",
       ["journald or application logs growing", "Docker images, container logs or volumes",
        "Old backups and panel database dumps kept on the same disk", "Leftover test artifacts; inode exhaustion with free space"],
       ["df -h / ; df -i /", "du -xh --max-depth=1 /var | sort -h | tail", "journalctl --disk-usage", "docker system df"],
       ["journalctl --vacuum-size=200M (the panel job vacuum_logs does this part)",
        "Remove old backups only after a newer verified one exists", "Move dumps off the host"],
       ["Do not delete the newest panel database dump: keep it until the next day after an update (pasarguard section 21)",
        "Do not prune Docker volumes on a node or panel host without the owner's yes"],
       ["scripts/node/health.sh", "install-recipes.md", "pasarguard.md section 21"]),

    _p("ram", "host", "Memory pressure",
       "مصرف RAM بالاست؛ ابتدا ببینید کدام پردازش یا تانل حافظه می‌گیرد، سپس هماهنگ ریستارت کنید.", "live",
       ["Tunnel clients with 4 MiB mux buffers grew to 1-2 GB after reconnect storms and were OOM-killed (incident 4)",
        "Pool bloat: far more tunnel connections than users (healthy mux is about 1 connection per 3 users)",
        "Hypervisor ballooning: unaccounted memory over 1 GB", "Another tenant's containers on a shared host"],
       ["free -m ; swapon --show", "ps -eo pid,rss,comm --sort=-rss | head", "journalctl -k --since -24h --no-pager | grep -i 'out of memory'",
        "On a relay compare users with tunnel connections per tunnel (scripts/relay/relay_conns.sh)"],
       ["Set mux_recievebuffer = 1048576 (1 MiB) in the tunnel tomls and do a coordinated restart of both ends, one tunnel at a time, off-peak",
        "Add 2-4 GB swap with vm.swappiness=10 as an OOM cushion"],
       ["High RSS alone is not bloat: memory follows load. Restart only when connections per user are far above normal (tunnels section 3.2)",
        "Do not restart one end of a Backhaul tunnel only: clients often do not re-establish (tunnels section 3.1)"],
       ["incidents.md 4", "tunnels.md sections 2, 3, 5", "capacity.md section 6", "node-lifecycle.md section 2"]),

    _p("cpu", "host", "High CPU",
       "مصرف CPU بالاست؛ ترافیک کاربران، تانل‌های مرده یا پردازش‌های دستی را بررسی کنید.", "live",
       ["Real peak load: a 2-core host at 66-75% is the upgrade point",
        "Stray hand-started processes (a deleted-binary tunnel tool spun at 16% each, incident 61)",
        "Dead reverse xDi links still burning half a core (incident 32); each xDi link a relay terminates costs CPU",
        "Another admin's node on a shared exit (incident 10); WARP inside Xray stalling at about 30k connections (incident 3)"],
       ["top -b -n1 | head -15 ; ps -eo pid,pcpu,comm,args --sort=-pcpu | head",
        "ls -l /proc/PID/exe ; tr '\\0' ' ' < /proc/PID/cmdline",
        "docker stats --no-stream",
        "systemctl list-units --type=service --state=running | grep -E 'backhaul|backpack|gre'"],
       ["Disable confirmed dead links on both ends", "Move a location that has a healthy alternative relay off a saturated relay; do not remove the newest one",
        "GRE instead of xDi where the datacenter passes it (a 1-core relay dropped from 60% to 1%)"],
       ["Do not stop a process you did not start without asking the operator (incident 61)",
        "Never offload a relay by leaving a name on one relay only (incident 62)"],
       ["incidents.md 3, 10, 32, 61, 62", "capacity.md sections 5, 12", "tunnels.md section 16"]),

    _p("steal", "host", "CPU steal (noisy hypervisor)",
       "steal بالاست: میزبان مجازی شلوغ است؛ شواهد زمان‌دار جمع کنید و به سرویس‌دهنده تیکت بدهید، ارتقای هسته کمکی نمی‌کند.", "live",
       ["The provider oversells the host. Tiers: above 10% warn, above 15% the host is oversold, above 40% critical for a host with users"],
       ["head -1 /proc/stat ; vmstat 5 3", "sar -u (steal is column 7, idle column 8) for daily averages and the worst 10 minutes",
        "cat /proc/pressure/cpu (some avg60 above 35% is pressure)", "docker stats --no-stream for other tenants' containers"],
       ["Open a provider ticket with the numbers, timestamps and time zone", "Move the load or change provider"],
       ["Do not resize the plan to fix steal above 15%: resizing does not help (capacity section 13)",
        "Do not decide from a single sample"],
       ["capacity.md sections 2, 13", "incidents.md 10"]),

    _p("retrans", "path", "High TCP retransmits",
       "ارسال مجدد TCP بالاست: مسیر یا میزبان مشکل دارد؛ مسیر هر رله را با سوکت‌های واقعی کاربران بسنجید نه فقط ping.", "live",
       ["A bad or throttled relay-exit path (incident 64: one relay's users had 5x the retransmission while ping and bulk tests were clean)",
        "tcp_mtu_probing=1 on a lossy link collapsed the MSS (incident 12)",
        "Provider network or upload cap on the exit", "Host uplink problem: loss to 1.1.1.1 is not the censor"],
       ["nstat -az TcpRetransSegs TcpOutSegs (about 1% normal, 5% or more is trouble)",
        "ss -tin state established '( sport = :PORT )' dst RELAY_IP | grep -oE 'bytes_sent:[0-9]+|bytes_retrans:[0-9]+' per relay",
        "sysctl net.ipv4.tcp_mtu_probing", "ping -c 100 1.1.1.1"],
       ["tcp_mtu_probing=0 and restart that tunnel (incident 12)",
        "Move the worst relay's port from kernel DNAT to an exit-dialed tunnel without flushing conntrack (tunnels section 19)",
        "Universally degraded exit: keep timestamped evidence and open a provider ticket or replace the host"],
       ["Do not judge a relay-exit pair by ping or nc throughput alone (incident 64)",
        "Do not call a new path stable before the next-day check (incident 18)"],
       ["capacity.md sections 8, 11", "tunnels.md section 19", "incidents.md 12, 64"]),

    _p("conntrack", "kernel", "conntrack table nearly full",
       "جدول conntrack نزدیک پر شدن است؛ مقدارهای زنده را با فایل sysctl مقایسه کنید، نه فقط فایل.", "live",
       ["The 5-day established timeout filled the table with dead mobile flows",
        "Limits reset to kernel defaults after a reboot: sysctl.d runs before nf_conntrack loads (incidents 27, 74)",
        "Table sized for a relay but the host is an exit with the default 65k table"],
       ["sysctl net.netfilter.nf_conntrack_max net.netfilter.nf_conntrack_count net.netfilter.nf_conntrack_tcp_timeout_established",
        "dmesg | grep -c 'nf_conntrack: table full'", "lsmod | grep nf_conntrack ; ls /etc/modules-load.d/", "grep -r conntrack /etc/sysctl.d/"],
       ["Apply live without a restart: nf_conntrack_max at least 262144 (1048576 on DNAT relays) and tcp_timeout_established about 7200 (10800 on relays)",
        "Load the module early via /etc/modules-load.d/nf_conntrack.conf and re-apply sysctl from the DNAT unit (ExecStartPost)",
        "scripts/node/host_tune.sh audits and applies the baseline"],
       ["A sysctl file is not proof: always compare the live value (incident 74)",
        "Do not flush conntrack on a live relay: existing flows would be cut (node-lifecycle section 12)"],
       ["capacity.md sections 7, 13", "incidents.md 27, 74"]),

    _p("failed_units", "host", "Failed systemd units",
       "سرویس‌های systemd ناموفق دارد؛ لاگ را بخوانید و تانل‌های فعال‌شده ولی متوقف را هم بررسی کنید.", "live",
       ["A tunnel, DNAT or node service crash-looping", "A half-finished package upgrade", "A bad config edit (incident 7: a shell mistake wrote an IP into a buffer setting)"],
       ["systemctl --failed --no-pager", "systemctl status UNIT -l --no-pager ; journalctl -u UNIT --since -1h --no-pager | tail -50",
        "systemctl list-unit-files --state=enabled | grep -E 'backhaul|backpack|relay-dnat|gre-' then systemctl is-active UNIT (--failed misses these)",
        "dpkg --audit"],
       ["Restart the unit after reading its log (job service_restart); for a tunnel use the coordinated restart of both ends",
        "After any batch edit grep every edited config for the value you meant to write"],
       ["systemctl is-active proves nothing for a tunnel: a dead tunnel stays active",
        "Do not restart a retired server's client: stop AND disable (incident 14)"],
       ["tunnels.md sections 1, 3, 5", "incidents.md 7, 14"]),

    _p("reboot_required", "host", "Reboot needed after updates",
       "سرور برای اعمال آپدیت نیاز به ریبوت دارد؛ در ساعت کم‌ترافیک، یکی‌یکی و پس از بررسی dpkg.", "live",
       ["Kernel or library updates are waiting for a reboot"],
       ["cat /var/run/reboot-required /var/run/reboot-required.pkgs", "dpkg --audit (must be empty)", "ss -tlnp (note the SSH listener ports first)",
        "docker ps -a (stopped containers with restart: always return after a reboot)", "debconf-show grub-pc and lsblk on cloned images"],
       ["Reboot one server at a time, least risky first and the panel host last, outside 16:00-21:00 UTC; run the after-reboot checks (playbook rebooted)",
        "Pin an intentionally stopped container first: docker update --restart=unless-stopped NAME"],
       ["Never reboot with dpkg --audit not empty (a half-configured bootloader is a gamble, incident 70)",
        "Never reboot or upgrade a second relay while the first one's SSH is unconfirmed (incident 71)"],
       ["node-lifecycle.md sections 7, 9, 10", "incidents.md 69, 70, 71"]),

    _p("ping", "path", "Relays cannot reach a foreign server (ICMP)",
       "رله‌های ایران این سرور را ping نمی‌کنند؛ با سه مبدأ و تست داده علت را جدا کنید، ICMP به‌تنهایی حکم نیست.", "live",
       ["Exit down (Xray, ports, disk, keep-alive): fails from relays, other in-country servers and abroad",
        "Exit IP blacklisted in-country: fails from every in-country server, works from abroad",
        "One relay's egress filtered toward that IP: fails from that relay only",
        "ICMP handled separately from TCP: 40% ping loss with healthy TCP, or 0% loss with dead TCP"],
       ["From each failing relay: ping -c 20 EXIT_IP ; a TLS request through the Reality fallback and a 10 MB download to the exit port",
        "From another in-country server in a different datacenter and from a foreign server: the same probes",
        "ping -c 20 1.1.1.1 as a control (loss there points at the host or its uplink)",
        "Compare: relay-bad/other-bad/abroad-bad = exit down; relay-bad/other-bad/abroad-ok = blacklisted; relay-bad/other-ok = relay egress"],
       ["Cheapest first: remove that relay from the location's DNS (keep at least two relays on every name); switch the relay's mode; move the tunnel client to another exit with the same token; new exit IP",
        "Reverse xDi or GRE where one direction is filtered (see playbooks relay_egress and relay_filtered)"],
       ["Never conclude from ping alone and never from a single relay (the panel only raises it when relays agree)",
        "Do not touch DNS before two independent probes and the exit side agree (incident 40)"],
       ["iran-filtering.md sections 1, 3, 4", "incidents.md 8, 40"]),

    _p("ssl_expiry", "cert", "Certificate expiring or invalid",
       "گواهی نزدیک انقضا یا نامعتبر است؛ علت شکست تمدید را بخوانید و بعد از تمدید در مسیر پنل/نود کپی و ریستارت کنید.", "live",
       ["Auto-renew off or failing", "Renewal depends on a relay forwarding port 80 that a cleanup removed (incident 11)",
        "Names now point at in-country relays, so HTTP validation from abroad fails (pasarguard section 20)",
        "Renewed but never deployed to the panel or node certificate paths"],
       ["certbot certificates", "systemctl list-timers | grep certbot", "journalctl -u certbot --since -7d --no-pager | tail -50",
        "openssl s_client -connect HOST:443 -servername HOST </dev/null 2>/dev/null | openssl x509 -noout -dates",
        "ss -ltn | grep ':80 '"],
       ["certbot renew (job cert_renew), then copy fullchain.pem and privkey.pem to the paths in UVICORN_SSL_CERTFILE/KEYFILE and restart the panel",
        "When names point at in-country relays move the certificate to DNS-01 validation before it expires"],
       ["Never remove a relay's port 80 forward in a cleanup (incident 11)",
        "Do not turn Cloudflare's proxy off before the panel has its own certificate for the name (pasarguard section 20)"],
       ["incidents.md 11", "pasarguard.md sections 11, 20", "tunnels.md section 3"]),

    _p("ssl_auto_renew_off", "cert", "Certificate auto-renew not active",
       "تمدید خودکار گواهی‌ها فعال نیست؛ certbot.timer را بررسی و در صورت تأیید مالک فعال کنید.", "live",
       ["certbot.timer disabled or not running", "Cron renewal removed", "Certificates from acme.sh without its cron"],
       ["systemctl list-timers | grep certbot", "systemctl is-enabled certbot.timer", "crontab -l | grep -E 'certbot|acme'"],
       ["systemctl enable --now certbot.timer, or restore the renewal cron"],
       ["Do not delete certificates (job cert_delete) unless you proved nothing uses them"],
       ["pasarguard.md section 20", "incidents.md 11"]),

    _p("ssl_renew_failed", "cert", "Last certbot renewal failed",
       "آخرین تمدید خودکار certbot ناموفق بوده؛ معمولاً DNS، پورت ۸۰ یا مسیر .well-known علت است.", "live",
       ["DNS no longer points where validation expects", "Port 80 not forwarded or taken by another service",
        "The .well-known challenge path blocked", "Names moved behind in-country relays so validators abroad cannot reach them"],
       ["journalctl -u certbot --no-pager | tail -80", "certbot renew --dry-run", "ss -ltnp | grep ':80 '", "dig +short NAME"],
       ["Fix the validation path (webroot method when nginx owns port 80), or switch to DNS-01"],
       ["Do not remove the relay forward of port 80 that renewal relies on (incident 11)"],
       ["incidents.md 11", "pasarguard.md section 20"]),

    # ---- codes added by the sibling detectors (live once their code is in the issue source) ----
    _p("rebooted", "lifecycle", "Server rebooted",
       "سرور ریبوت شده؛ چک‌لیست پس از ریبوت را اجرا کنید: واحدها، DNAT، conntrack زنده، لیسنرها، نه فقط وضعیت «connected».", AUTO,
       ["Provider reboot or maintenance", "Kernel panic or OOM", "Someone rebooted it, or an unattended upgrade did"],
       ["uptime -s ; cat /proc/sys/kernel/random/boot_id (a changed boot_id is the reboot proof)", "systemctl --failed --no-pager ; dpkg --audit",
        "ss -tlnp and compare with the baseline (SSH ports, every inbound port on exits)", "sysctl net.ipv4.ip_forward ; nft list tables (DNAT table present)",
        "sysctl net.netfilter.nf_conntrack_max net.netfilter.nf_conntrack_tcp_timeout_established (live values, not files)",
        "systemctl list-unit-files --state=enabled | grep -E 'backhaul|backpack|relay-dnat|gre-' then systemctl is-active each",
        "docker ps -a ; on exits docker logs --since 3m NODE 2>&1 | grep -c Unavailable",
        "Flood ping each tunnel peer: ping -f -s 1200 -c 300 PEER (0% loss is the test, not unit state)", "sysctl net.ipv4.tcp_congestion_control (BBR can fall back to cubic)"],
       ["Re-apply conntrack limits live; restart the DNAT unit if its table is gone",
        "Exit with a stopped Xray: save the node again in the panel (restarts the core in seconds), with the owner's yes",
        "Add a relay-allowlist entry for tunnel peers and restart the service that reads it (incident 67)"],
       ["Do not trust the panel's node status 'connected' after a reboot (incidents 51, 60, 63)",
        "Do not reboot several servers at once: least risky first, panel host last"],
       ["node-lifecycle.md section 10", "pasarguard.md section 12", "incidents.md 27, 51, 60, 67, 74", "DETECTION-CATALOG.md (after-reboot verification)"]),

    _p("ip_changed", "lifecycle", "Server public IP changed",
       "IP عمومی سرور عوض شده؛ هشت جا را بررسی کنید: تانل‌ها، DNS، allowlist، nft، SSH و اسکریپت‌ها.", AUTO,
       ["The provider rotated the address (sometimes after mobile carriers blocked the old one)", "Rebuild or migration to another host"],
       ["Confirm it is the same server (host key, uptime, running units) from the operator's network and from a phone hotspot",
        "grep -R OLD_IP /etc on the relay and the exits ; nft list ruleset | grep OLD_IP", "dig +short NAME for each record that pointed at the old address"],
       ["Order: back up files as FILE.bak-DATE; relay's own listeners and allowlists; each exit's tunnel client one at a time (wait for the link before the next); other relays' DNAT lines; DNS last, new record added before the old one is deleted; operator SSH alias and scripts",
        "Re-measure every tunnel mode on the new range (GRE, xDi both ways, direct download)",
        "A rotated relay must not be any location's only relay"],
       ["Never leave a name without an address while moving DNS", "Do not assume the new range is as open as the old one: treat it as a new relay (tunnels section 17)"],
       ["node-lifecycle.md section 15", "tunnels.md section 17", "incidents.md 29, 39, 77"]),

    _p("resized", "lifecycle", "Cores or RAM dropped (resized or rebuilt)",
       "تعداد هسته یا RAM کم شده؛ احتمالاً ریسایز یا بازسازی توسط سرویس‌دهنده؛ کلید میزبان و سرویس‌ها را تأیید کنید.", AUTO,
       ["The provider resized, migrated or rebuilt the server (new cloud-init instance id, sometimes new SSH host keys)"],
       ["nproc ; free -m ; df -h /", "ls /var/lib/cloud/instances/ (a new directory means a new instance)", "ssh-keyscan HOST | ssh-keygen -lf - from a foreign server; the fingerprint must match",
        "ls -l /etc/ssh/ssh_host_*_key.pub ; uptime -s ; journalctl -u ssh --since -24h | grep Accepted"],
       ["Re-take the baseline, then check tunnels, DNAT and nodes came back (reboot verification)", "Tell the operator in case nobody on their side did it"],
       ["Do not accept a changed host key blindly: verify from another vantage point first, back up known_hosts, then replace the entry"],
       ["node-lifecycle.md section 13", "incidents.md 45, 54"]),

    _p("blacklisted", "path", "Exit IP blacklisted in-country",
       "IP خروجی از همهٔ رله‌ها قطع است ولی از خارج کار می‌کند؛ احتمالاً در داخل مسدود شده؛ تانل معکوس یا IP جدید.", AUTO,
       ["Destination-IP blacklist after heavy direct DNAT traffic (one exit took 60-80 GB/h and was blocked after about 8 hours)"],
       ["From 2-3 in-country relays and from one foreign server: ping -c 20 EXIT_IP and a TLS request to the location port (000 means blocked)",
        "Per-node user counts in the panel for a sudden collapse"],
       ["Move the tunnel client to the blocked server with the same token (reverse tunnels survive the blacklist; the relay side is untouched)",
        "Reverse xDi (the exit dials the relay); new exit IP and keep a spare; spread high-volume locations over several exit IPs"],
       ["Do not assume a working DNAT path is safe for good: the trigger is probabilistic or volume-related",
        "Remove a relay from DNS only if it reaches no exit and every name keeps two relays"],
       ["iran-filtering.md sections 1-4", "incidents.md 2", "tunnels.md section 4"]),

    _p("relay_egress", "path", "One relay cannot reach an exit (egress filter)",
       "فقط یک رله به این خروجی نمی‌رسد؛ فیلتر خروجی همان رله؛ حالت آن مسیر را عوض کنید یا از DNS آن لوکیشن خارجش کنید.", AUTO,
       ["The relay's datacenter egress allow-list lets only some foreign ranges through", "Per-destination ICMP/TCP filtering from that relay's DC"],
       ["Run the same target set from a relay in a different datacenter", "From the failing relay: ping -c 20 EXIT_IP ; curl --resolve through the Reality fallback ; a 10 MB download",
        "From abroad to the relay's own port (inbound test)"],
       ["Switch that relay's mode for the location (tunnel to DNAT when inbound from abroad is filtered; DNAT to reverse tunnel when the exit IP is blocked)",
        "Remove that relay from the location's DNS only while the location keeps two other relays"],
       ["Do not conclude from ping: always add a data test", "Do not leave the location with a single relay"],
       ["iran-filtering.md sections 1-4", "incidents.md 1, 46"]),

    _p("relay_filtered", "path", "Relay's datacenter filters many paths",
       "فیلتر در سطح دیتاسنتر رله: چند خروجی هم‌زمان از آن رله قطع هستند؛ حالت تانل را عوض کنید و از سرویس‌دهنده IP دیگری بخواهید.", AUTO,
       ["Inbound-from-abroad data blackhole: tunnels show established but carry 0 bytes (incident 1)",
        "ICMP from abroad to that datacenter filtered: every xDi link there dies the same night (incidents 17, 52, 55)",
        "A new IP range filtered harder than the old one (incident 39)"],
       ["From a foreign server: TLS to a relay port (000 while TCP connects means blackhole); tcpdump shows only retransmits",
        "scripts/node/bpstatus.sh peer loss and handshake did not complete; ping the relay from several exits",
        "Per-flow UDP allowance test: send 20+ packets on one flow and count arrivals with tcpdump on the far side"],
       ["DNAT mode (relay dials the node) rescues a relay whose outbound still works; GRE where the datacenter passes it (measure per relay)",
        "Disable dead links on both ends at once, then ask the provider for an address in another range"],
       ["Do not retry a dying xDi link in a loop: each retry burns another pair (incident 55)",
        "Do not add xDi links to a relay faster than one at a time, checking plain ping from abroad after each"],
       ["iran-filtering.md section 2", "tunnels.md sections 15-17", "incidents.md 1, 17, 52, 55"]),

    _p("quota", "quota", "Traffic quota running out",
       "سهمیهٔ ترافیک ماهانه رو به پایان است؛ پیش از قطع‌شدن رله، آن را از بخشی از DNS کم کنید و رلهٔ دوم را نگه دارید.", AUTO,
       ["Relays carry each user byte twice (2-3 TB/day per relay is typical)", "Two relays reaching their caps on the same morning"],
       ["vnstat -d or sar -n DEV history against the provider cap", "List the locations that have exactly one working relay: those go dark first"],
       ["Warn days ahead and drop the relay from some DNS names while every name keeps two other relays; stagger quota sizes or renewal dates",
        "Add a second relay of a different path type to single-relay locations"],
       ["Never leave a name on one relay, even temporarily (incident 62)"],
       ["capacity.md sections 9, 12", "incidents.md 21, 37, 62, 68"]),

    _p("quota_pair", "quota", "Two relays run out of quota close together",
       "حجم دو رله با فاصلهٔ کمتر از ۴۸ ساعت تمام می‌شود؛ یکی را زودتر شارژ کنید تا یک موقعیت بی‌رله نماند.", AUTO,
       ["Both relays carry each user byte twice and were bought with similar caps and renewal dates"],
       ["Per relay: vnstat -d or sar -n DEV history against the provider cap, and the panel quota forecast (days_left)",
        "List the locations that have these relays as their only two working relays"],
       ["Stagger the quota sizes or renewal dates; top up the sooner one first",
        "Move some DNS names to a third relay while each name keeps two other relays; when one goes dark add the other to the affected names before deleting the dead record"],
       ["Never leave a name on one relay, even temporarily (incident 62)", "Do not wait for the cut: a suspended host looks like a datacenter outage with no ping and no SSH"],
       ["capacity.md section 12", "incidents.md 21, 37, 62, 68"]),

    _p("load_per_core", "host", "Load per core too high",
       "بار به‌ازای هر هسته زیاد است؛ idle، steal و فشار CPU را ببینید، نه فقط مگابیت.", AUTO,
       ["More runnable work than cores: users at peak, tunnel CPU, stray processes", "Heavy steal making cores slower than they look"],
       ["uptime ; nproc", "cat /proc/pressure/cpu ; vmstat 5 3", "ps -eo pid,pcpu,comm --sort=-pcpu | head", "docker stats --no-stream"],
       ["Shift DNAT weights or re-point one relay to an idle sibling exit (7,500/7,500 split took a busy exit from load 4.8 to 2.7)",
        "Upgrade order: 2-core exits with real users, hosts with steal above 40% (change provider), the busiest exit, relays with pressure above 35%"],
       ["Do not judge a host by Mbit alone", "Do not call a low reading 'no users' before the relay link, DNS names and node status are checked"],
       ["capacity.md sections 10, 13"]),

    # ---- detectors planned (agent 0.3.0, panel truth, probes) ----
    _p("listener_missing", "tunnel", "Expected port is not listening",
       "پورت مورد انتظار گوش نمی‌دهد؛ پنل می‌گوید «connected» ولی Xray روی هیچ پورتی نیست؛ لیسنرها را مستقیم بررسی کنید.", "planned",
       ["Xray core stopped while the node container is up", "Tunnel unit up on paper but its forward port closed", "SSH or inbound port taken or lost after an upgrade"],
       ["ss -ltnp", "ss -ltn | grep ':PORT ' for each inbound port of the exit (from the panel host list: address, port)", "docker logs --since 3m NODE 2>&1 | grep -c 'Code: Unavailable'"],
       ["Exit core stopped: save the node again with the same address and port in the panel (restarts it in seconds)", "Tunnel: coordinated restart of both ends"],
       ["Do not trust node status or systemctl is-active as proof of a working listener"],
       ["pasarguard.md section 12", "incidents.md 51, 60, 63", "tunnels.md section 1"]),

    _p("tunnel_unit_inactive", "tunnel", "Tunnel unit enabled but not running",
       "یک واحد تانل enable است ولی اجرا نمی‌شود؛ systemctl --failed آن را نشان نمی‌دهد.", "planned",
       ["The unit stopped and never restarted", "A stale client of a retired server is enabled and steals a relay's control channel after reboot (incident 14)"],
       ["systemctl list-unit-files --state=enabled | grep -E 'backhaul|backpack|relay-dnat|gre-' then systemctl is-active UNIT", "journalctl -u UNIT --since -1h --no-pager | tail -50"],
       ["Start it after reading why it stopped; retired servers: stop AND disable every client"],
       ["Do not rely on systemctl --failed or is-active for tunnel health"],
       ["tunnels.md sections 1, 3", "incidents.md 14, 32"]),

    _p("node_core_stopped", "node", "Node connected but Xray stopped",
       "نود در پنل «connected» است ولی Xray متوقف شده؛ صفر کاربر با همهٔ مسیرهای سالم؛ ذخیرهٔ مجدد نود آن را برمی‌گرداند.", "planned",
       ["The panel did not resend Start after a reboot", "Panel database lock timeouts and 5-15 s API responses (backend not initialized)", "Keep-alive timeout stopped the core"],
       ["On the exit: ss -ltn for each inbound port", "docker logs --since 3m NODE 2>&1 | grep -E 'Unavailable|keep alive timeout'", "Panel log: Stream failed ... backend not initialized"],
       ["Save each affected node again with the same address and port (scripts/panel/node_edit.sh), with the owner's yes", "Raise keep_alive (for example 600): no restart needed"],
       ["Do not trust the dashboard's node status", "Restarting the panel restarts Xray on every node: only off-peak and announced"],
       ["pasarguard.md sections 2, 3, 12", "incidents.md 51, 60, 63"]),

    _p("dnat_table_missing", "tunnel", "DNAT table gone",
       "جدول DNAT رله بعد از ریبوت یا تغییر از بین رفته؛ پورت‌های لوکیشن بسته‌اند.", "planned",
       ["The oneshot unit that reloads the nft file did not run after reboot", "A new tunnel type was added but an older DNAT table still overrides its ports (prerouting DNAT wins over a local listener)"],
       ["nft list tables ; nft list table ip relay_dnat", "sysctl net.ipv4.ip_forward", "systemctl status relay-dnat --no-pager"],
       ["Restart the DNAT unit (reloads the persisted nft file and keeps existing flows); after changing a relay's tunnel type remove NAT rules for ports the new tunnel owns"],
       ["Do not flush a remote host's whole firewall as a rollback; validate candidates with nft -c -f FILE first"],
       ["tunnels.md sections 6, 14, 16", "incidents.md 27, 73"]),

    _p("conntrack_limits_reset", "kernel", "conntrack limits reset to defaults",
       "حدود conntrack بعد از ریبوت به پیش‌فرض برگشته (۸۱۹۲ ورودی و timeout پنج‌روزه)؛ مقدار زنده را با فایل مقایسه کنید.", "planned",
       ["sysctl.d ran before the nf_conntrack module loaded, so the lines were skipped"],
       ["sysctl net.netfilter.nf_conntrack_max net.netfilter.nf_conntrack_tcp_timeout_established", "ls /etc/modules-load.d/ ; grep -r conntrack /etc/sysctl.d/"],
       ["Apply the limits live; add /etc/modules-load.d/nf_conntrack.conf; re-apply sysctl from the DNAT unit (ExecStartPost)"],
       ["Do not accept the file as evidence of the live value"],
       ["capacity.md sections 7, 13", "incidents.md 27, 74"]),

    _p("quota_exhausted", "quota", "Quota exhausted, host dark",
       "سهمیهٔ ترافیک تمام شده و سرور روی همهٔ پورت‌ها از همهٔ مبدأها قطع است؛ اول پنل سرویس‌دهنده را ببینید.", "planned",
       ["The provider suspended the host at its monthly traffic cap (the same relay twice in one week)"],
       ["TCP data ports from an in-country server and SSH from two other servers all fail; far ends of its tunnels show no traffic", "Provider panel: quota and billing"],
       ["Top up; tunnel clients that backed off may need a restart; meanwhile add the other relay to the affected names before deleting the dead record"],
       ["Do not debug routes before checking the provider's quota and billing", "Do not judge 'down' by ping or one SSH banner"],
       ["incidents.md 21, 37, 68", "capacity.md section 12"]),

    _p("panel_path_broken", "panel", "Panel or subscription path broken through a relay",
       "مسیر پنل یا اشتراک از یک آدرس خراب است؛ POST ربات‌ها گیر می‌کند؛ هر آدرس رکورد را با GET کامل و POST تست کنید.", "planned",
       ["An xDi/ICMP-carried or throttled relay stalls request bodies: POST/PUT answered 400 after about 16 minutes while GET works (incidents 30, 47, 56)",
        "The direct panel IP answers small requests but delivers 0 bytes of a page from some datacenters (incident 34)", "Panel behind Cloudflare's proxy resolved to throttled addresses (incident 42)"],
       ["For every address in the panel record: a realistic full-page download and a wrong-password POST login (must return 401 in under a second) (scripts/relay/panel_path_check.sh)",
        "Panel access log: 400s with huge durations from a relay's tunnel address"],
       ["Remove the offending address from the record; keep a written list of addresses that must never be in it and re-run the check after anyone edits DNS", "Bots abroad: pin the panel name to the panel IP in /etc/hosts"],
       ["Never put an xDi/ICMP-carried relay behind the panel domain", "Do not test with a page load only: test a POST and a download"],
       ["pasarguard.md sections 16, 20", "incidents.md 22, 30, 34, 42, 47, 56"]),

    _p("db_pool_exhausted", "panel", "Panel database pool exhausted",
       "استخر اتصال دیتابیس پنل پر شده (QueuePool limit)؛ مقدار را بالا ببرید و کانتینر را recreate کنید نه restart.", "planned",
       ["SQLALCHEMY_POOL_SIZE/MAX_OVERFLOW still at the defaults 5+5 on a busy panel"],
       ["docker logs --since 3h pasarguard-pasarguard-1 2>&1 | grep -c QueuePool", "Startup line 'Database pool: size=5, max_overflow=5'", "SHOW VARIABLES LIKE 'max_connections' (151 default on MySQL)"],
       ["Set SQLALCHEMY_POOL_SIZE=20 and SQLALCHEMY_MAX_OVERFLOW=40 after backing up .env, then docker compose up -d --force-recreate pasarguard"],
       ["docker compose restart does not re-read env_file: the old pool stays", "Do not declare the panel broken before Uvicorn is running or login returns 401 (a restart can take minutes)"],
       ["pasarguard.md section 19", "incidents.md 41"]),

    _p("backup_old", "panel", "Newest panel backup too old",
       "جدیدترین بکاپ دیتابیس پنل قدیمی یا خراب است؛ سن و gzip -t را بسنجید.", "planned",
       ["The dump job stopped", "The dump failed integrity (gzip -t) or is far smaller than usual"],
       ["ls -l --time-style=full-iso on the dump directory", "gzip -t NEWEST_DUMP ; compare its size with the previous dumps"],
       ["Take a fresh dump before any panel update; keep it until the next day (a rollback restores code, not schema)"],
       ["Do not treat a restore as verified: the panel only keeps the record"],
       ["pasarguard.md section 21", "incidents.md 72"]),

    _p("update_rolled_back", "panel", "Scheduled panel update rolled back",
       "به‌روزرسانی زمان‌بندی‌شدهٔ پنل برگشت خورده یا ناموفق بود؛ تعداد نودهای متصل را قبل و بعد مقایسه کنید.", "planned",
       ["Fewer nodes connected after the update, so the script re-tagged the old image and recreated the container", "Dump failed so the update aborted"],
       ["Update script log (UPDATE FAILED / rollback lines)", "docker ps -a ; docker logs --since 30m pasarguard-pasarguard-1 2>&1 | tail -80", "Connected node count before and after"],
       ["Read the release notes for a major or minor step, then retry in a quiet window; keep the dump"],
       ["A rollback cannot undo a schema migration: do not delete the dump", "Do not combine a panel update with a host reboot in the same window"],
       ["pasarguard.md section 21", "incidents.md 66, 72"]),

    _p("dns_dead_relay", "dns", "DNS record points at a dead relay",
       "یکی از رکوردهای DNS یک لوکیشن به رلهٔ مرده اشاره می‌کند و تقریباً هر اتصال دوم گیر می‌کند؛ هر رکورد را جدا تست کنید.", "planned",
       ["A round-robin name has a relay address that no longer answers from the vantage point (incident 75)"],
       ["dig +short NAME then one probe per address (data test, not ping)", "Probe from an in-country server and, when carriers differ, from a phone hotspot of each carrier"],
       ["Remove the dead member only after the others pass a real-data test; add a relay back only after it passes from an in-country probe and a mobile network"],
       ["Never remove the last record of a name; never leave a name empty (incident 35)", "Do not pull a relay carrying many users on one failed probe (incident 40)"],
       ["incidents.md 35, 40, 75, 76", "cloudflare.md"]),

    _p("single_relay_location", "topology", "Location with only one working relay",
       "این لوکیشن فقط یک رلهٔ سالم دارد؛ هر رویداد سهمیه یا فیلتر آن را می‌خواباند؛ رلهٔ دوم با نوع مسیر متفاوت اضافه کنید.", "planned",
       ["Offloading a saturated relay left names on one relay (incident 62)", "A relay's address keeps rotating (incident 29)"],
       ["List each DNS name and the relays it resolves to; mark names with fewer than two healthy relays"],
       ["Add a second relay of a different path type (reverse xDi next to reverse backhaul covers quota and filtering events)"],
       ["Relieve a saturated relay by adding capacity, not by leaving names on one relay"],
       ["capacity.md section 12", "incidents.md 21, 29, 62"]),

    _p("gre_one_sided", "tunnel", "GRE link answers from one end only",
       "لینک GRE فقط از یک سمت پاسخ می‌دهد؛ از هر دو انتها ping بزنید و یک سمت را ریستارت کنید.", "planned",
       ["The relay-side GRE unit stopped answering while the exit side still pings fine"],
       ["Ping the tunnel address from both ends", "ip -s link show GRE_IF on both ends"],
       ["Restart one end (systemctl restart gre-NAME), recheck from both ends, then restart the other if needed"],
       ["A one-sided ping check would call a broken link healthy: always test both directions"],
       ["tunnels.md section 16", "incidents.md 57"]),

    _p("xdi_link_dead", "tunnel", "xDi link dead while its unit is active",
       "لینک xDi مرده ولی واحد active است؛ لینک مرده CPU می‌سوزاند و لینک‌های زنده را خراب می‌کند؛ از دو سمت غیرفعالش کنید.", "planned",
       ["Per-destination ICMP filtering from the relay's datacenter (forward links die, links the exits dial survive)", "A second dialed link on one exit (only one per exit host works)",
        "Too much ICMP closed the relay to xDi entirely"],
       ["scripts/node/bpstatus.sh : peer loss 100% and handshake did not complete", "tcpdump -ni any icmp and host EXIT on the relay when an allowlist may drop echoes"],
       ["Disable the dead link on both ends; prefer exit-dials-relay; one dialed xDi link per exit; test the final combination; re-check next day"],
       ["Never report a fresh link as stable before the next-day check", "Do not restart a dying link in a loop"],
       ["tunnels.md section 15", "incidents.md 17, 19, 31, 52, 55, 67"]),

    _p("throttled_pair", "path", "Throttled relay-exit pair",
       "جفت رله-خروجی کند یا محدود شده؛ سوکت‌های واقعی کاربران را به تفکیک رله بسنجید و مسیر را عوض کنید.", "planned",
       ["Filtering that hurts real user flows while synthetic tests pass (incident 64)", "Direct DNAT to one exit gave 0.02 MB per connection while a tunnel to the same exit passed 100-140 Mbit (incident 53)"],
       ["On the exit: ss -tin state established '( sport = :PORT )' dst RELAY | grep -oE 'bytes_sent:[0-9]+|bytes_retrans:[0-9]+' per relay; compare MB per connection and retransmission"],
       ["Move that relay's port from kernel DNAT to an exit-dialed tunnel (spare port first, then the real port, then delete the DNAT rules; do not flush conntrack)",
        "Or send the port over the relay's healthy GRE link to a sibling exit and DNAT from there"],
       ["Do not trust ping or nc throughput for a pair"],
       ["tunnels.md sections 16, 19", "incidents.md 53, 64"]),

    _p("provider_throttle", "host", "Provider throttle or upload cap",
       "سرویس‌دهنده پهنای باند را محدود کرده (سقف ثابت با CPU آزاد)؛ شواهد جمع کنید؛ تانل مشکل را حل نمی‌کند.", "planned",
       ["Monthly usage crossed a threshold and the provider throttled the port", "The provider caps upload while download is at line rate"],
       ["Throughput pinned to an exact value, retransmits at 5% or more, loss to 1.1.1.1", "Download 25-50 MB from speed.cloudflare.com on the node under load; compare upload from the exit to a foreign server"],
       ["Show timestamped evidence to the provider or replace the server (reuse tunnel tokens so no relay changes); move a location's relay path to another exit over a new GRE link"],
       ["Do not blame a tunnel before measuring the exit's own upload from a foreign server"],
       ["capacity.md section 3", "incidents.md 9, 38, 43", "node-lifecycle.md section 12"]),

    _p("inbound_no_group", "panel", "Inbound or host in no group",
       "اینباند یا هاست در هیچ گروهی نیست؛ لوکیشن با وجود مسیر سالم هیچ کاربری ندارد.", "planned",
       ["A new node or inbound got hosts and DNS but no group", "The panel's inbound-cleanup deleted new tags before the panel restarted (incident 13)"],
       ["scripts/panel/inbound_groups.py (read-only listing)", "Per-node user counts staying at zero with healthy paths"],
       ["Add the inbound to the same groups as the other tunnel inbounds, then restart the panel once (announced, off-peak)"],
       ["Do not write nodes to the panel database and forget to restart: the running panel keeps nodes in memory"],
       ["pasarguard.md sections 2, 5, 18", "incidents.md 13, 36, 49"]),

    _p("ssh_listener_lost", "access", "SSH listener lost",
       "sshd روی پورت تعریف‌شده گوش نمی‌دهد؛ اگر این رله jump host دیگران است، مسیر دوم و کنسول سرویس‌دهنده لازم است.", "planned",
       ["An OpenSSH upgrade on a custom port left nothing listening (incident 71)", "Host overloaded so banners time out while data ports answer (incident 58)"],
       ["ss -tlnp | grep sshd (before and after any upgrade)", "sshd -T | grep -i -E 'port|pubkey'"],
       ["Restart ssh from the provider console; keep a second jump path"],
       ["Never upgrade openssh-server on someone's only jump host without a second jump and console access"],
       ["incidents.md 58, 71", "node-lifecycle.md sections 1, 9"]),

    _p("dpkg_audit_dirty", "host", "Half-configured packages (bootloader)",
       "dpkg --audit خالی نیست؛ بوت‌لودر نیمه‌پیکربندی‌شده؛ ریبوت قمار است.", "planned",
       ["A template-cloned server whose bootloader setting names a disk that does not exist (incident 70)"],
       ["dpkg --audit", "debconf-show grub-pc ; lsblk"],
       ["debconf-set-selections with the real disk, then dpkg --configure -a; confirm /boot has the new kernel and dpkg --audit is empty"],
       ["Do not reboot in this state"],
       ["incidents.md 70", "node-lifecycle.md section 9"]),

    _p("domain_hold", "dns", "Domain on hold or expired",
       "همهٔ کانفیگ‌های یک دامنه با هم از کار افتاده‌اند؛ ثبت دامنه clientHold یا منقضی شده است؛ پیش از دست‌زدن به سرور dig و whois بزنید.", "planned",
       ["The registration lapsed and the registrar removed the nameservers"],
       ["dig @1.1.1.1 NAME ; whois DOMAIN (status clientHold, expiry date)"],
       ["Renew the domain, or move the hosts to new names in a live domain"],
       ["Do not touch servers when every config under one domain fails together before checking DNS and registration"],
       ["incidents.md 65"]),

    _p("keepalive_stop", "node", "Node stopped Xray on keep-alive timeout",
       "نود به‌خاطر keep-alive خودش Xray را متوقف کرده؛ keep_alive را بالا ببرید.", "planned",
       ["A one-minute network blip between panel and node stops Xray when keep_alive is 60"],
       ["docker logs --since 168h NODE 2>&1 | grep 'keep alive timeout' (count per week)", "Panel-to-node path: ping and curl -w '%{time_connect} %{time_appconnect}'"],
       ["Raise keep_alive (for example 600): costs nothing, applies at the next Start"],
       ["Do not blame the tunnels: they are fine when this happens"],
       ["pasarguard.md sections 3, 15", "incidents.md 6, 25"]),

    _p("auth_bruteforce", "access", "Failed panel logins from one source",
       "ورودهای ناموفق مکرر به پنل از یک آدرس؛ ابتدا بپرسید ربات/ریسلر با رمز قدیمی است یا حدس رمز.", "planned",
       ["A reseller integration with an old password, or password guessing (about 20,000 failures a day went unnoticed for four days)"],
       ["scripts/panel/auth_failures.sh : failures and successes per source"],
       ["After the operator confirms, block the source with a dedicated nftables table (scripts/panel/blocklist.sh)"],
       ["Never block a relay or 127.0.0.1: every user and bot behind a relay shares those addresses"],
       ["pasarguard.md section 17", "incidents.md 33"]),

    _p("panel_stopped", "panel", "Panel container stopped",
       "کانتینر پنل متوقف است؛ نودها هنوز سرویس می‌دهند و کسی متوجه نمی‌شود؛ docker ps -a را در هر ممیزی ببینید.", "planned",
       ["Stopped by hand: restart: always does not restart it until the Docker daemon restarts, then a reboot revives it"],
       ["docker ps -a (Exited panel or database containers)"],
       ["Ask whether it should come back; pin an intentional stop with docker update --restart=unless-stopped NAME"],
       ["Do not reboot a host with a deliberately stopped container before pinning it"],
       ["incidents.md 69", "pasarguard.md section 2"]),

    _p("stale_tunnel_client", "tunnel", "Retired server's tunnel client still enabled",
       "کلاینت تانل یک سرور بازنشسته هنوز enable است و بعد از ریبوت کانال کنترل رله را می‌دزدد.", "planned",
       ["Retirement only stopped the client; a reboot revived it and it reconnected with the same token"],
       ["systemctl list-unit-files --state=enabled | grep -E 'backhaul|backpack' and compare with the inventory"],
       ["Stop AND disable every client of a retired server; move configs to a dated backup directory"],
       ["Never print or pipe tokens to the terminal: they are the tunnel's identity"],
       ["tunnels.md section 3", "incidents.md 14", "node-lifecycle.md section 6"]),
]

GENERIC = _p(
    "generic", "generic", "Unknown issue code",
    "برای این کد راهنمای اختصاصی ثبت نشده؛ شواهد مسئله را بخوانید و با تاریخچهٔ آن مقایسه کنید.", "planned",
    ["Not yet curated: use the issue's title, evidence and suggestion from /api/v1/issues"],
    ["GET /api/v1/issues/history?range=7d for the same key (how often and how long)", "journalctl -p warning -b --no-pager | tail -50 on the server",
     "Compare with sibling servers of the same role"],
    ["Follow the issue's own suggestion text; ask the owner before any change"],
    ["Do not change a server on the strength of one signal", "Do not leave a location with one relay"],
    ["SKILL.md (operating rules)"],
)


def normalise(code: str) -> str:
    """`ping:203.0.113.5` is the ping playbook; anything before the first colon names the theme."""
    return (code or "").split(":")[0].strip().lower()


@lru_cache(maxsize=1)
def _table() -> Dict[str, Dict[str, Any]]:
    out = {}
    for e in _ENTRIES:
        item = dict(e)
        if item["detector"] == AUTO:
            item["detector"] = _live(item["code"])
        out[item["code"]] = item
    return out


def all_playbooks() -> List[Dict[str, Any]]:
    return list(_table().values())


def find(code: str) -> Tuple[Dict[str, Any], bool]:
    """The playbook for an issue code and whether it was a real match (False means the generic fallback)."""
    hit = _table().get(normalise(code))
    return (hit, True) if hit else (GENERIC, False)


def first_check(code: str) -> Optional[str]:
    pb, ok = find(code)
    return pb["checks"][0] if ok and pb["checks"] else None
