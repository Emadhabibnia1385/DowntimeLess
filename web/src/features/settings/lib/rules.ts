// The kinds of alert the master knows and the numbers that tune each.
export type RuleId =
	| "offline"
	| "cpu"
	| "ram"
	| "disk"
	| "steal"
	| "retrans"
	| "conntrack"
	| "ping"
	| "ssl"
	| "failed_units"
	| "reboot"
	| "rebooted"
	| "ip_changed"
	| "resized"
	| "blacklisted"
	| "relay_egress"
	| "relay_filtered"
	| "load_per_core"
	| "quota"
	| "quota_pair"
	| "listener_missing"
	| "unit_stopped"
	| "unit_crashloop"
	| "container_down"
	| "container_restarting"
	| "container_unhealthy"
	| "container_revived"
	| "dnat_missing"
	| "ip_forward_off"
	| "conntrack_limits_reset"
	| "conntrack_drops"
	| "oom_kill"
	| "inode_high"
	| "journal_big"
	| "time_unsynced"
	| "reboot_pending_pkgs"
	| "node_down"
	| "node_silent"
	| "node_usage_drop"
	| "inbound_without_group"
	| "reseller_quota"
	| "panel_version_changed"
	| "panel_errors"
	| "dnat_dead_target"
	| "dnat_unknown_target"
	| "relay_forward_broken";

export type RuleUnit = "percent" | "days" | "minutes" | "count" | "mb";
export type RuleGroup = "host" | "paths" | "services" | "kernel" | "panel";

export type Rule = {
	id: RuleId;
	group: RuleGroup;
	/** Settings key of the warning level, if the alert has one. */
	warn?: string;
	/** Settings key of the critical level, if the alert has one. */
	crit?: string;
	unit: RuleUnit | null;
	/** The two numbers are separate limits (relay and exit, say), not warning and critical. */
	unordered?: boolean;
};

export const RULE_GROUPS: readonly RuleGroup[] = ["host", "paths", "services", "kernel", "panel"];

/** The largest number each unit accepts in the form. */
export const UNIT_MAX: Record<RuleUnit, number> = {
	percent: 100,
	days: 365,
	minutes: 1440,
	count: 67_108_864,
	mb: 1_000_000,
};

export const RULES: readonly Rule[] = [
	{ id: "offline", group: "host", unit: null },
	{ id: "cpu", group: "host", warn: "cpu_warn", unit: "percent" },
	{ id: "ram", group: "host", warn: "ram_warn", unit: "percent" },
	{ id: "disk", group: "host", warn: "disk_warn", crit: "disk_crit", unit: "percent" },
	{ id: "steal", group: "host", warn: "steal_warn", unit: "percent" },
	{ id: "load_per_core", group: "host", unit: null },
	{ id: "retrans", group: "host", warn: "retrans_warn", unit: "percent" },
	{ id: "conntrack", group: "host", crit: "conntrack_crit", unit: "percent" },
	{ id: "failed_units", group: "host", unit: null },
	{ id: "reboot", group: "host", unit: null },
	{ id: "rebooted", group: "host", unit: null },
	{ id: "ip_changed", group: "host", unit: null },
	{ id: "resized", group: "host", unit: null },
	{ id: "ping", group: "paths", warn: "loss_warn", crit: "loss_crit", unit: "percent" },
	{ id: "blacklisted", group: "paths", unit: null },
	{ id: "relay_egress", group: "paths", unit: null },
	{ id: "relay_filtered", group: "paths", unit: null },
	{ id: "relay_forward_broken", group: "paths", unit: null },
	{ id: "quota", group: "paths", unit: null },
	{ id: "quota_pair", group: "paths", unit: null },
	{ id: "ssl", group: "paths", warn: "ssl_warn_days", crit: "ssl_crit_days", unit: "days" },
	{ id: "listener_missing", group: "services", unit: null },
	{ id: "unit_stopped", group: "services", unit: null },
	{ id: "unit_crashloop", group: "services", unit: null },
	{ id: "container_down", group: "services", unit: null },
	{ id: "container_restarting", group: "services", unit: null },
	{ id: "container_unhealthy", group: "services", unit: null },
	{ id: "container_revived", group: "services", unit: null },
	{ id: "dnat_missing", group: "kernel", unit: null },
	{ id: "dnat_dead_target", group: "kernel", unit: null },
	{ id: "dnat_unknown_target", group: "kernel", unit: null },
	{ id: "ip_forward_off", group: "kernel", unit: null },
	{
		id: "conntrack_limits_reset",
		group: "kernel",
		warn: "ct_max_relay",
		crit: "ct_max_exit",
		unit: "count",
		unordered: true,
	},
	{ id: "conntrack_drops", group: "kernel", unit: null },
	{ id: "oom_kill", group: "kernel", unit: null },
	{ id: "inode_high", group: "kernel", warn: "inode_warn", unit: "percent" },
	{ id: "journal_big", group: "kernel", warn: "journal_warn_mb", unit: "mb" },
	{ id: "time_unsynced", group: "kernel", warn: "ntp_unsynced_min", unit: "minutes" },
	{ id: "reboot_pending_pkgs", group: "kernel", unit: null },
	{ id: "node_down", group: "panel", crit: "node_down_min", unit: "minutes" },
	{ id: "node_silent", group: "panel", crit: "node_unavailable", unit: "count" },
	{
		id: "node_usage_drop",
		group: "panel",
		warn: "node_drop_pct",
		crit: "node_others_pct",
		unit: "percent",
		unordered: true,
	},
	{ id: "inbound_without_group", group: "panel", unit: null },
	{
		id: "reseller_quota",
		group: "panel",
		warn: "reseller_warn",
		crit: "reseller_crit",
		unit: "percent",
	},
	{ id: "panel_version_changed", group: "panel", unit: null },
	{ id: "panel_errors", group: "panel", unit: null },
];

export const onKey = (id: RuleId) => `on_${id}`;

/** Settings that are a switch but not an alert's own on/off. */
export const QUOTA_BASIS = "quota_basis";

/** The master's defaults, used until the real values arrive. */
export const DEFAULT_SETTINGS: Record<string, number> = {
	cpu_warn: 90,
	steal_warn: 10,
	ram_warn: 90,
	disk_warn: 85,
	disk_crit: 95,
	retrans_warn: 5,
	conntrack_crit: 85,
	loss_warn: 10,
	loss_crit: 50,
	ssl_warn_days: 21,
	ssl_crit_days: 7,
	ct_max_relay: 65536,
	ct_max_exit: 262144,
	ct_timeout_max: 43200,
	inode_warn: 85,
	journal_warn_mb: 1024,
	ntp_unsynced_min: 10,
	node_down_min: 5,
	node_unavailable: 5,
	node_drop_pct: 30,
	node_others_pct: 70,
	reseller_warn: 85,
	reseller_crit: 95,
	reseller_hours: 24,
	[QUOTA_BASIS]: 0,
	...Object.fromEntries(RULES.map((rule) => [onKey(rule.id), 1])),
};
