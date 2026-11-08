"""Sample command output and configs for the 0.3.0 checks, written to match Debian 12 / Ubuntu 22.04 hosts."""

SS_TULNP = """udp   UNCONN 0      0          127.0.0.53%lo:53         0.0.0.0:*    users:(("systemd-resolve",pid=612,fd=13))
udp   UNCONN 0      0            0.0.0.0:443        0.0.0.0:*    users:(("backhaul",pid=901,fd=9))
udp   UNCONN 0      0            0.0.0.0:51820      0.0.0.0:*
tcp   LISTEN 0      4096         0.0.0.0:22         0.0.0.0:*    users:(("sshd",pid=700,fd=3))
tcp   LISTEN 0      4096            [::]:22            [::]:*    users:(("sshd",pid=700,fd=4))
tcp   LISTEN 0      4096         0.0.0.0:2222       0.0.0.0:*    users:(("sshd",pid=700,fd=5))
tcp   LISTEN 0      65535              *:443              *:*    users:(("backhaul",pid=901,fd=7))
tcp   LISTEN 0      4096       127.0.0.1:45678      0.0.0.0:*    users:(("python3",pid=1200,fd=4))
tcp   LISTEN 0      4096       127.0.0.1:62789      0.0.0.0:*    users:(("xray",pid=1300,fd=4))
tcp   LISTEN 0      4096       127.0.0.1:0          0.0.0.0:*    users:(("weird",pid=1,fd=1))
tcp   LISTEN 0      511          0.0.0.0:80         0.0.0.0:*    users:(("nginx",pid=800,fd=6),("nginx",pid=801,fd=6))
"""

UNIT_FILES = """ssh.service                 enabled enabled
backhaul-de1.service        enabled enabled
backpack-bpde.service       enabled enabled
relay-dnat.service          enabled enabled
wattun@.service             enabled enabled
nginx.service               enabled enabled
cron.service                enabled enabled
dl-agent.service            enabled
"""

LIST_UNITS = """backhaul-de1.service   loaded active     running      Backhaul de1
● backpack-bpde.service  loaded activating auto-restart BackPack bpde
relay-dnat.service     loaded inactive   dead         Relay DNAT table relay_dnat
wattun@nl.service      loaded active     running      WatTunnel nl
myapp.service          loaded activating auto-restart My app
ssh.service            loaded active     running      OpenBSD Secure Shell server
"""

UNIT_SHOW = {
    "backhaul-de1.service": ("active", "running", "0", "enabled"),
    "backpack-bpde.service": ("activating", "auto-restart", "17", "enabled"),
    "relay-dnat.service": ("inactive", "dead", "0", "enabled"),
    "nginx.service": ("active", "running", "0", "enabled"),
    "dl-agent.service": ("active", "running", "2", "enabled"),
    "wattun@nl.service": ("active", "running", "1", "enabled"),
    "myapp.service": ("activating", "auto-restart", "5", "disabled"),
}


def systemctl_show(names, fields=("Id", "ActiveState", "SubState", "NRestarts", "UnitFileState")):
    blocks = []
    for n in names:
        active, sub, restarts, ufs = UNIT_SHOW.get(n, ("inactive", "dead", "[not set]", ""))
        values = {"Id": n, "ActiveState": active, "SubState": sub, "NRestarts": restarts, "UnitFileState": ufs,
                  "LoadState": "loaded" if n in UNIT_SHOW else "not-found"}
        blocks.append("\n".join("%s=%s" % (f, values[f]) for f in fields))
    return "\n\n".join(blocks) + "\n"


PANEL_ID = "3f1c" + "0" * 60
DB_ID = "a2b0" + "0" * 60
NODE_ID = "c9d0" + "0" * 60
OLD_ID = "e1f0" + "0" * 60

DOCKER_PS = (
    "%s\tpasarguard-pasarguard-1\tpasarguard/panel:latest\trunning\tUp 3 hours\n"
    "%s\tpasarguard-mysql-1\tmariadb:lts\trunning\tUp 3 hours (healthy)\n"
    "%s\tnode-de\tpasarguard/node:v0.1.4\trunning\tUp 2 days\n"
    "%s\told-node\tpasarguard/node@sha256:9b1f00aa\texited\tExited (255) 4 days ago\n"
) % (PANEL_ID, DB_ID, NODE_ID, OLD_ID)

DOCKER_INSPECT = "\n".join([
    '{"id":"%s","restarts":0,"policy":"always","health":null,"status":"running","exit_code":0,"oom":false,'
    '"started":"2026-11-08T07:15:02.123456789Z","image":"pasarguard/panel:latest"}' % PANEL_ID,
    '{"id":"%s","restarts":2,"policy":"always","health":"healthy","status":"running","exit_code":0,"oom":false,'
    '"started":"2026-11-08T07:14:55.5Z","image":"mariadb:lts"}' % DB_ID,
    '{"id":"%s","restarts":41,"policy":"unless-stopped","health":"unhealthy","status":"running","exit_code":0,"oom":false,'
    '"started":"2026-11-09T01:00:00Z","image":"pasarguard/node:v0.1.4@sha256:77aa"}' % NODE_ID,
    '{"id":"%s","restarts":0,"policy":"no","health":null,"status":"exited","exit_code":255,"oom":true,'
    '"started":"0001-01-01T00:00:00Z","image":"pasarguard/node@sha256:9b1f00aa"}' % OLD_ID,
]) + "\n"

NFT_TABLES = """table inet filter
table ip relay_dnat
table ip nat
table inet dl_acct
"""

NFT_RULESET = """table inet filter {
\tchain input {
\t\ttype filter hook input priority filter; policy accept;
\t}
}
table ip relay_dnat {
\tchain pre {
\t\ttype nat hook prerouting priority -110; policy accept;
\t\ttcp dport 21001 counter packets 10 bytes 600 dnat to 198.51.100.10:21001
\t\ttcp dport 21002 counter packets 0 bytes 0 dnat to 10.77.1.2:21002
\t}
\tchain post {
\t\ttype nat hook postrouting priority 90; policy accept;
\t\tip daddr 198.51.100.10 tcp dport 21001 counter packets 10 bytes 600 masquerade
\t}
}
table ip nat {
\tchain DOCKER {
\t\tiifname != "docker0" meta l4proto tcp tcp dport 8080 counter packets 0 bytes 0 dnat to 172.17.0.2:80
\t}
}
"""

NF_CONNTRACK_STAT = (
    "entries  clashres found new invalid ignore delete chainlength insert insert_failed drop early_drop error "
    "expect_new expect_create expect_delete search_restart\n"
    "00000a1c  00000000 00000000 00000000 0000001f 00000000 00000000 00000000 00000000 00000002 00000003 00000001 "
    "00000000 00000000 00000000 00000000 00000005\n"
    "00000a1c  00000000 00000000 00000000 00000004 00000000 00000000 00000000 00000000 00000001 0000000d 00000000 "
    "00000000 00000000 00000000 00000000 00000000\n"
)

VMSTAT = "nr_free_pages 123456\npgfault 99999\noom_kill 3\noom_kill_extra 9\n"

JOURNAL_USAGE = "Archived and active journals take up 1.2G in the file system.\n"
JOURNAL_USAGE_OLD = "Journals take up 56.0M on disk.\n"

TIMEDATECTL = "NTPSynchronized=yes\n"

SSHD_T = "port 22\nport 2222\npermitrootlogin without-password\npasswordauthentication no\nkbdinteractiveauthentication no\n"

UFW_CONF = "# /etc/ufw/ufw.conf\n#\n\n# Set to yes to start on boot.\nENABLED=yes\nLOGLEVEL=low\n"

# every value below that contains "SECRET" must never reach a report
BACKHAUL_SERVER = """[server]
bind_addr = "0.0.0.0:3080"
transport = "tcpmux"
token = "SECRET-backhaul-server-9f8e7d"   # shared with the client
keepalive_period = 75
nodelay = true
mux_con = 8
log_level = "info"
ports = [
  "443",
  "8443=127.0.0.1:8443",
  "2000-2003=10.0.0.2:2000",
]
"""

BACKHAUL_CLIENT = """[client]
remote_addr = "203.0.113.20:3080"
transport = "tcpmux"
token = 'SECRET-backhaul-client-1a2b3c'
connection_pool = 8
"""

BACKPACK_L3 = """mode = "dial"
carrier = "xdi"
addr = "10.77.1.1/30"
peer_ip = "10.77.1.2"
iface = "bpde"
token = "SECRET-backpack-l3-token-0000"
psk = "SECRETpskvalue1234567890abcdefABCDEF"
"""

RATHOLE_SERVER = """[server]
bind_addr = "0.0.0.0:2333"
default_token = "SECRET-rathole-default"

[server.services.ssh]
token = "SECRET-rathole-ssh"
bind_addr = "0.0.0.0:5202"
"""

FRPC_TOML = """serverAddr = "198.51.100.30"
serverPort = 7000
auth.method = "token"
auth.token = "SECRET-frp-auth-token"

[[proxies]]
name = "web"
type = "tcp"
localIP = "127.0.0.1"
localPort = 443
remotePort = 6443
"""

WATTUN_YML = """name: nl
mode: client
token: "wat1:SECRETwattunTokenAAAAAAAAAAAAAAAAAAAA"
remote: 198.51.100.40:8443
carrier: wss
password: SECRET-wattun-password
"""

PANEL_OUTPUT = (
    '{"version":"5.6.0","nodes":[{"id":1,"name":"de-1","address":"198.51.100.10","port":62050,"status":"connected",'
    '"message":"","keep_alive":60},{"id":2,"name":"nl-1","address":"198.51.100.11","port":62050,"status":"error",'
    '"message":"auth failed token=SECRETnodeTokenValue1234567890abcdef for mysql+asyncmy://root:SECRETdbpass@db:3306/pg",'
    '"keep_alive":600,"api_key":"SECRET-node-api-key"}],'
    '"usage":{"hour_start":1762646400,"last":[{"node_id":1,"users":812,"bytes":51234567890}],'
    '"prev":[{"node_id":1,"users":790,"bytes":49000000000},{"node_id":2,"users":3,"bytes":1200}]},'
    '"admins":[{"name":"reseller-a","used":900000000000,"limit":1000000000000,"hashed_password":"SECRET$2b$12$hash"},'
    '{"name":"root","used":null,"limit":null}],'
    '"inbounds_without_group":["tunnel-fi"],"user_status":{"active":5200,"limited":40,"expired":310,"on_hold":12,'
    '"disabled":7,"weird":2},"errors":["admins:OperationalError","bad entry with SECRET"],'
    '"db_url":"mysql+asyncmy://root:SECRETdbpass@db:3306/pg","env":{"JWT":"SECRET-jwt"}}\n'
)
