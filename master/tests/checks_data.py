"""Agent 0.3.x `checks` and `panel` blocks shaped like the real fleet's, for the phase 2 and 3 rule tests."""
import copy

GIB = 1024 ** 3

LISTENERS = [
    {"proto": "tcp", "port": 22, "proc": "sshd"}, {"proto": "tcp", "port": 443, "proc": "xray"},
    {"proto": "tcp", "port": 8443, "proc": "xray"}, {"proto": "tcp", "port": 21001, "proc": "backhaul"},
    {"proto": "udp", "port": 51820, "proc": None}, {"proto": "udp", "port": 0, "proc": "xray", "count": 40},
]


def checks(**over):
    """A healthy relay's checks; override any block by name."""
    base = {
        "listeners": copy.deepcopy(LISTENERS),
        "units": [
            {"name": "backhaul-de.service", "enabled": True, "active": "active", "sub": "running", "restarts": 0},
            {"name": "relay-dnat.service", "enabled": True, "active": "active", "sub": "exited", "restarts": 0},
            {"name": "nginx.service", "enabled": True, "active": "active", "sub": "running", "restarts": 0},
        ],
        "conntrack": {"module_loaded": True, "count": 12000, "max": 1048576, "tcp_established_timeout": 10800,
                      "insert_failed": 0, "drop": 0, "early_drop": 0},
        "containers": [
            {"name": "pasarguard-node-1", "image": "pasarguard/node:latest", "state": "running", "status": "Up 3 days", "restarts": 0,
             "health": None, "policy": "always", "exit_code": 0, "oom_killed": False, "started_at": 1},
        ],
        "container_logs": [{"container": "pasarguard-node-1", "unavailable": 0, "keepalive": 0, "queuepool": 0, "certfail": 0}],
        "nft": {"tables": ["ip relay_dnat", "inet filter"], "relay_dnat": True, "dnat_rules": 12, "dnat_by_table": {"relay_dnat": 12}, "ip_forward": 1},
        "tunnels": {"configs": [{"name": "de", "type": "backhaul", "mode": "server", "transport": "tcp", "ports": [21001], "peer": None,
                                 "iface": None, "unit": "backhaul-de.service", "active": "active"}], "links": []},
        "kernel": {"congestion": "bbr", "qdisc": "fq", "mtu_probing": 0, "ip_forward": 1, "reserved_ports": "21001", "swappiness": 10,
                   "oom_kill": 0, "boot_id": "boot-a", "ntp_synced": True, "inode_pct": 12.0, "journal_mb": 300.0},
        "security": {"ufw": "inactive", "fail2ban": "active", "password_auth": False, "sshd_ports": [22]},
        "apt": {"dpkg_audit": 0, "held_docker": False, "reboot_required_pkgs": 0},
    }
    base.update(over)
    return base


def panel(**over):
    """The real panel's shape: 23 nodes (22 connected, 1 disabled), 40 resellers (some above 96%), the real user counts."""
    nodes = [{"id": i, "name": "node-%02d" % i, "address": "198.51.100.%d" % (100 + i), "port": 62050, "status": "connected",
              "message": "", "keep_alive": 600} for i in range(1, 24)]
    nodes[22]["status"] = "disabled"
    admins = []
    for i in range(40):
        limit = (200 + 10 * i) * GIB
        share = 0.97 if i in (3, 17) else 0.965 if i == 25 else 0.5 + (i % 7) * 0.05
        admins.append({"name": "reseller%02d" % i, "used": int(limit * share), "limit": limit})
    admins.append({"name": "sudo", "used": 5 * GIB, "limit": None})
    data = {
        "container": "pasarguard-pasarguard-1", "version": "5.6.0", "nodes": nodes,
        "usage": {"hour_start": None, "last": [{"node_id": n["id"], "users": 300, "bytes": 40 * GIB} for n in nodes[:22]],
                  "prev": [{"node_id": n["id"], "users": 310, "bytes": 42 * GIB} for n in nodes[:22]]},
        "admins": admins, "inbounds_without_group": ["wg0"],
        "user_status": {"active": 8410, "limited": 2331, "expired": 2514, "on_hold": 291, "disabled": 24, "other": 0},
        "errors": [],
    }
    data.update(over)
    return data
