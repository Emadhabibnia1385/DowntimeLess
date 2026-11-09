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


# ---- guides for people (lang=fa) ----
from app.features.reports import guides_fa  # noqa: E402

PERSIAN = re.compile(r"[؀-ۿ]")
ISSUE_SOURCES = ("overview/service.py", "overview/detectors.py", "overview/forwards.py", "ssl/service.py", "checks/host.py",
                 "checks/panel.py", "checks/drift.py", "checks/quality.py")


def test_the_code_scan_sees_every_issue_constructor():
    # a code passed as a variable would hide from raised_codes and so from the guide test below
    for rel in ISSUE_SOURCES:
        src = (playbooks._FEATURES / rel).read_text(encoding="utf-8")
        calls = re.findall(r"(?<![\w.])(?<!def )(?:_issue|make)\(\s*\w+,\s*(\S)", src)
        assert all(c == '"' for c in calls), (rel, calls)
        literal = re.findall(r'"code":\s*(?!code,)(\S)', src)  # `"code": code` is make() itself
        assert all(c == '"' for c in literal), (rel, literal)


def test_every_raised_code_has_a_complete_persian_guide():
    missing = [c for c in playbooks.raised_codes() if not guides_fa.guide(c)]
    assert not missing, "issue codes without a Persian guide: %s" % missing
    for g in guides_fa.index() + [guides_fa.GENERIC]:
        for key in ("title", "meaning", "why"):
            assert PERSIAN.search(g[key]), (g["code"], key)
        for key in ("checks", "fixes", "fixed_when", "never"):
            assert g[key], (g["code"], key)
        for step in g["checks"] + g["fixes"]:
            assert PERSIAN.search(step["text"]), (g["code"], step)
            assert step["cmd"] is None or (step["cmd"].strip() and not PERSIAN.search(step["cmd"])), (g["code"], step)


def test_guides_name_real_codes_and_keep_the_commands_unchanged():
    for g in guides_fa.index():
        pb, matched = playbooks.find(g["code"])
        assert matched, g["code"]
        english = " ".join(pb["checks"] + pb["fixes"] + pb["never"])
        for step in g["checks"] + g["fixes"]:
            if step["cmd"]:
                assert step["cmd"] in english, (g["code"], step["cmd"])
    generic = " ".join(playbooks.GENERIC["checks"])
    assert all(s["cmd"] in generic for s in guides_fa.GENERIC["checks"] if s["cmd"])


def test_guide_checks_are_read_only():
    for g in guides_fa.index() + [guides_fa.GENERIC]:
        for step in g["checks"]:
            assert not (step["cmd"] and CHANGES_A_SERVER.search(step["cmd"])), (g["code"], step["cmd"])


def test_lang_fa_over_the_api(owner):
    lst = owner.get("/api/v1/reports/playbooks?lang=fa").json()["playbooks"]
    titled = {p["code"]: p for p in lst if p["title_fa"]}
    assert set(playbooks.raised_codes()) <= set(titled)
    assert all(PERSIAN.search(p["meaning_fa"]) for p in titled.values())
    assert all(p["title_fa"] is None for p in owner.get("/api/v1/reports/playbooks").json()["playbooks"])
    r = owner.get("/api/v1/reports/playbooks/node_down:7?lang=fa").json()
    assert r["matched"] and r["guide_fa"]["code"] == "node_down" and r["guide_fa"]["fixed_when"]
    assert owner.get("/api/v1/reports/playbooks/disk").json()["guide_fa"] is None
    r = owner.get("/api/v1/reports/playbooks/never_heard_of_it?lang=fa").json()
    assert not r["matched"] and r["guide_fa"]["code"] == "generic"
    r = owner.get("/api/v1/reports/playbooks/quota_exhausted?lang=fa").json()  # planned: no guide for people yet
    assert r["matched"] and r["guide_fa"]["code"] == "generic"
    md = owner.get("/api/v1/reports/playbooks/conntrack?lang=fa&format=md").text
    assert "```\nsysctl net.netfilter.nf_conntrack_max" in md and "از کجا بفهمیم رفع شد" in md
    assert owner.get("/api/v1/reports/playbooks?lang=de").status_code == 422


def test_the_index_names_the_first_fix_command_of_each_guide(owner):
    lst = {p["code"]: p for p in owner.get("/api/v1/reports/playbooks?lang=fa").json()["playbooks"]}
    assert lst["dnat_dead_target"]["fix_cmd_fa"].startswith("cp -a /etc/nftables-relay-dnat.nft")
    assert lst["drift_ipset"]["fix_cmd_fa"].startswith("cp -a /etc/nyxon/access.conf")
    assert lst["ip_forward_off"]["fix_cmd_fa"] == "sysctl -w net.ipv4.ip_forward=1"
    assert lst["container_revived"]["fix_cmd_fa"] is None or isinstance(lst["container_revived"]["fix_cmd_fa"], str)
    assert all(p["fix_cmd_fa"] is None for p in owner.get("/api/v1/reports/playbooks").json()["playbooks"])

