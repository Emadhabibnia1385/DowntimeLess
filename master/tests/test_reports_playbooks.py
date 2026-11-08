import re

from app.features.reports import playbooks

SIBLING_CODES = ["quota_pair", "rebooted", "ip_changed", "resized", "blacklisted", "relay_egress", "relay_filtered", "quota", "load_per_core"]
PLANNED_THEMES = [
    "quota_exhausted", "panel_path_broken", "db_pool_exhausted", "backup_old", "update_rolled_back", "dns_dead_relay",
]
# phase 2 (host checks) and phase 3 (panel truth): live because their codes are in checks/host.py and checks/panel.py
CHECK_CODES = [
    "listener_missing", "unit_stopped", "unit_crashloop", "container_down", "container_restarting", "container_unhealthy",
    "container_revived", "dnat_missing", "ip_forward_off", "conntrack_limits_reset", "conntrack_drops", "oom_kill", "inode_high",
    "journal_big", "time_unsynced", "reboot_pending_pkgs", "node_down", "node_silent", "node_usage_drop", "inbound_without_group",
    "reseller_quota", "panel_version_changed", "panel_errors",
]
LIVE = ["offline", "disk", "ram", "cpu", "steal", "retrans", "conntrack", "failed_units", "reboot_required", "ping", "agent_missing", "ssl_expiry", "ssl_auto_renew_off", "ssl_renew_failed"]
CHANGES_A_SERVER = re.compile(r"(^|[;|]\s*|&&\s*)(rm|reboot|shutdown|kill|pkill)\s|systemctl (restart|stop|start|enable|disable)|sysctl -w|nft (-f|delete|add|flush)|docker (compose|restart|stop|rm|prune)|apt(-get)? (install|upgrade|remove)|certbot renew\b(?! --dry-run)|>\s*/(?!dev/null)")


def test_every_code_the_issue_source_raises_has_its_own_playbook():
    codes = playbooks.raised_codes()
    assert {"offline", "disk", "ram", "cpu", "steal", "retrans", "conntrack", "failed_units", "reboot_required", "agent_missing", "ping", "ssl_expiry"} <= set(codes)
    for code in codes:
        pb, matched = playbooks.find(code)
        assert matched and pb["code"] == playbooks.normalise(code), code


def test_required_themes_are_covered_and_flagged():
    table = {p["code"]: p for p in playbooks.all_playbooks()}
    assert len(table) >= 25
    for code in LIVE:
        assert table[code]["detector"] == "live", code
    for code in PLANNED_THEMES:
        assert table[code]["detector"] == "planned", code
    for code in CHECK_CODES:
        assert table[code]["detector"] == "live", code
        assert code in playbooks.raised_codes(), code
    for code in SIBLING_CODES:
        assert table[code]["detector"] == "live", code  # the detectors are merged: their codes are in the issue source
        assert code in playbooks.raised_codes()


def test_entries_are_complete_persian_summarised_and_cite_the_skill():
    for p in playbooks.all_playbooks():
        for key in ("causes", "checks", "fixes", "never", "source"):
            assert p[key], (p["code"], key)
        assert re.search(r"[؀-ۿ]", p["summary_fa"]), p["code"]
        assert p["detector"] in ("live", "planned") and p["title"]
        assert all(s.split()[0].endswith((".md", ".sh", ".py")) for s in p["source"]), (p["code"], p["source"])


def test_checks_are_read_only():
    for p in playbooks.all_playbooks():
        for c in p["checks"]:
            assert not CHANGES_A_SERVER.search(c), (p["code"], c)


def test_unknown_codes_fall_back_and_ping_ip_is_the_ping_guide(owner):
    r = owner.get("/api/v1/reports/playbooks/ping:198.51.100.7").json()
    assert r["matched"] and r["playbook"]["code"] == "ping"
    r = owner.get("/api/v1/reports/playbooks/never_heard_of_it").json()
    assert not r["matched"] and r["playbook"]["code"] == "generic" and r["playbook"]["checks"]
    lst = owner.get("/api/v1/reports/playbooks").json()
    assert len(lst["playbooks"]) >= 25 and lst["principles"]
    assert "never" not in lst["playbooks"][0]  # the list is the index, details are per code
    md = owner.get("/api/v1/reports/playbooks/conntrack?format=md").text
    assert "## Read-only checks" in md and "nf_conntrack_max" in md and "## Never" in md
