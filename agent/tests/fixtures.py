"""Sample /proc, /sys and command output captured from typical Debian hosts."""

PROC_STAT_1 = """cpu  1000 0 500 8000 500 0 0 0 0 0
cpu0 500 0 250 4000 250 0 0 0 0 0
intr 12345
"""

# +400 jiffies in total: 160 idle + 20 iowait, 80 steal
PROC_STAT_2 = """cpu  1100 0 540 8160 520 0 0 80 0 0
cpu0 550 0 270 4080 260 0 0 40 0 0
intr 12400
"""

PROC_MEMINFO = """MemTotal:        4096000 kB
MemFree:          500000 kB
MemAvailable:    2560000 kB
Buffers:          100000 kB
"""

SNMP_HEAD = "Tcp: RtoAlgorithm RtoMin RtoMax MaxConn ActiveOpens PassiveOpens AttemptFails EstabResets CurrEstab InSegs OutSegs RetransSegs InErrs OutRsts\n"
PROC_SNMP_1 = "Ip: Forwarding DefaultTTL\nIp: 1 64\n" + SNMP_HEAD + \
    "Tcp: 1 200 120000 -1 100 200 3 4 50 100000 100000 400 0 10\nUdp: InDatagrams\nUdp: 10\n"
PROC_SNMP_2 = "Ip: Forwarding DefaultTTL\nIp: 1 64\n" + SNMP_HEAD + \
    "Tcp: 1 200 120000 -1 110 210 3 4 50 120000 110000 450 0 10\nUdp: InDatagrams\nUdp: 20\n"

PROC_NET_ROUTE = (
    "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
    "wg0\t00000000\t0100000A\t0003\t0\t0\t900\t00000000\t0\t0\t0\n"
    "eth0\t00000000\t0100A8C0\t0003\t0\t0\t100\t00000000\t0\t0\t0\n"
    "eth0\t0000A8C0\t00000000\t0001\t0\t0\t100\t00FFFFFF\t0\t0\t0\n"
)

IP_ROUTE = """default via 192.168.0.1 dev ens3 proto dhcp src 192.168.0.5 metric 100
192.168.0.0/24 dev ens3 proto kernel scope link src 192.168.0.5
"""

PING_OK = """PING 198.51.100.7 (198.51.100.7) 56(84) bytes of data.
64 bytes from 198.51.100.7: icmp_seq=1 ttl=57 time=41.0 ms

--- 198.51.100.7 ping statistics ---
5 packets transmitted, 5 received, 0% packet loss, time 1204ms
rtt min/avg/max/mdev = 40.100/41.200/42.000/0.700 ms
"""

PING_LOSSY = """--- 198.51.100.7 ping statistics ---
5 packets transmitted, 4 received, 20% packet loss, time 1204ms
rtt min/avg/max/mdev = 40.100/50.500/62.000/0.700 ms
"""

PING_DEAD = """PING 198.51.100.9 (198.51.100.9) 56(84) bytes of data.

--- 198.51.100.9 ping statistics ---
5 packets transmitted, 0 received, 100% packet loss, time 4098ms
"""

SYSTEMCTL_FAILED = """● fail2ban.service loaded failed failed Fail2Ban Service
● backup.timer   loaded failed failed Nightly backup
"""

SYSTEMCTL_FAILED_PLAIN = "fail2ban.service loaded failed failed Fail2Ban Service\n"

IPINFO = {"ip": "203.0.113.5", "city": "Falkenstein", "country": "DE", "org": "AS24940 Hetzner Online GmbH"}
IPWHO = {"success": True, "ip": "203.0.113.5", "city": "Falkenstein", "country_code": "DE",
         "connection": {"org": "Hetzner Online GmbH"}}
