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
	| "quota_pair";

export type Rule = {
	id: RuleId;
	/** Settings key of the warning level, if the alert has one. */
	warn?: string;
	/** Settings key of the critical level, if the alert has one. */
	crit?: string;
	unit: "percent" | "days" | null;
};

export const RULES: readonly Rule[] = [
	{ id: "offline", unit: null },
	{ id: "cpu", warn: "cpu_warn", unit: "percent" },
	{ id: "ram", warn: "ram_warn", unit: "percent" },
	{ id: "disk", warn: "disk_warn", crit: "disk_crit", unit: "percent" },
	{ id: "steal", warn: "steal_warn", unit: "percent" },
	{ id: "retrans", warn: "retrans_warn", unit: "percent" },
	{ id: "conntrack", crit: "conntrack_crit", unit: "percent" },
	{ id: "ping", warn: "loss_warn", crit: "loss_crit", unit: "percent" },
	{ id: "ssl", warn: "ssl_warn_days", crit: "ssl_crit_days", unit: "days" },
	{ id: "failed_units", unit: null },
	{ id: "reboot", unit: null },
	{ id: "rebooted", unit: null },
	{ id: "ip_changed", unit: null },
	{ id: "resized", unit: null },
	{ id: "blacklisted", unit: null },
	{ id: "relay_egress", unit: null },
	{ id: "relay_filtered", unit: null },
	{ id: "load_per_core", unit: null },
	{ id: "quota", unit: null },
	{ id: "quota_pair", unit: null },
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
	[QUOTA_BASIS]: 0,
	...Object.fromEntries(RULES.map((rule) => [onKey(rule.id), 1])),
};
