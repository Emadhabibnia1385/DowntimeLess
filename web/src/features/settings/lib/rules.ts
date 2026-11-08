// The kinds of alert the master knows, the numbers that tune each, and where each is delivered.
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
	| "reboot";

export type Rule = {
	id: RuleId;
	/** Settings key of the warning level, if the alert has one. */
	warn?: string;
	/** Settings key of the critical level, if the alert has one. */
	crit?: string;
	unit: "percent" | "days" | null;
	/** Also sent to the admins on Telegram, not only listed in the panel. */
	telegram: boolean;
};

export const RULES: readonly Rule[] = [
	{ id: "offline", unit: null, telegram: true },
	{ id: "cpu", warn: "cpu_warn", unit: "percent", telegram: false },
	{ id: "ram", warn: "ram_warn", unit: "percent", telegram: false },
	{ id: "disk", warn: "disk_warn", crit: "disk_crit", unit: "percent", telegram: false },
	{ id: "steal", warn: "steal_warn", unit: "percent", telegram: false },
	{ id: "retrans", warn: "retrans_warn", unit: "percent", telegram: false },
	{ id: "conntrack", crit: "conntrack_crit", unit: "percent", telegram: false },
	{ id: "ping", warn: "loss_warn", crit: "loss_crit", unit: "percent", telegram: false },
	{ id: "ssl", warn: "ssl_warn_days", crit: "ssl_crit_days", unit: "days", telegram: true },
	{ id: "failed_units", unit: null, telegram: false },
	{ id: "reboot", unit: null, telegram: false },
];

export const onKey = (id: RuleId) => `on_${id}`;

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
	...Object.fromEntries(RULES.map((rule) => [onKey(rule.id), 1])),
};
