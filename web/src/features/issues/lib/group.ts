import type { Issue } from "@/api/generated/model";
import { formatDuration, formatNumber, formatPercent, t } from "@/strings";

export type Severity = "critical" | "warning" | "info";
export type GroupItem = {
	id: string;
	serverId: number | null;
	serverName: string;
	to: "server" | "ssl" | "panel" | null;
	value: string;
	/** How many times this problem was active in the last 24 hours. */
	recent: number;
};
export type IssueGroup = {
	family: string;
	title: string;
	severity: Severity;
	suggestion: string;
	items: GroupItem[];
};

const RANK: Record<Severity, number> = { critical: 0, warning: 1, info: 2 };
const PERCENT_KEYS = [
	"steal_pct",
	"cpu_pct",
	"ram_pct",
	"disk_pct",
	"retrans_pct",
	"conntrack_pct",
	"inode_pct",
];
// PasarGuard panel issues open the panel page, where the node or reseller is a row
const PANEL_FAMILIES = new Set([
	"node_down",
	"node_silent",
	"node_usage_drop",
	"inbound_without_group",
	"reseller_quota",
	"panel_version_changed",
	"panel_errors",
]);
const list = (value: unknown): string => (Array.isArray(value) ? value.map(String).join(", ") : "");

/** "ping:1.2.3.4" and "ssl_expiry" both name a family of problems: the part before any colon. */
export const familyOf = (code: string): string => code.split(":")[0];

const num = (value: unknown): number | null => (typeof value === "number" ? value : null);

/** What to show beside a server: the measured level, the units, the days left. */
export function valueOf(issue: Issue): string {
	const e = issue.evidence as Record<string, unknown>;
	const family = familyOf(issue.code);
	for (const key of PERCENT_KEYS) {
		const v = num(e[key]);
		if (v !== null) return formatPercent(v);
	}
	if (family === "ping") {
		const loss = num(e.loss_pct);
		const relays = Array.isArray(e.relays) ? e.relays.length : 0;
		const by = relays ? ` (${t.issues.values.relays(formatNumber(relays))})` : "";
		return loss === null ? by.trim() : formatPercent(loss) + by;
	}
	if (family === "drift_ipset" || family === "drift_dnat") {
		const live = num(e.live);
		const file = num(e.file);
		if (live !== null && file !== null)
			return t.issues.values.liveVsFile(formatNumber(live), formatNumber(file));
	}
	if (family === "drift_sysctl" && Array.isArray(e.keys)) return list(e.keys);
	if (Array.isArray(e.units)) return e.units.join(", ");
	for (const key of ["ports", "containers", "inbounds", "errors"]) {
		if (Array.isArray(e[key])) return list(e[key]);
	}
	if (typeof e.reseller === "string") {
		const used = num(e.used_pct);
		return used === null ? e.reseller : `${e.reseller}: ${formatPercent(used)}`;
	}
	if (typeof e.node === "string") {
		const share = num(e.users_pct);
		return share === null ? e.node : `${e.node}: ${formatPercent(share)}`;
	}
	if (family === "conntrack_limits_reset") {
		const max = num(e.conntrack_max);
		return max === null ? "" : formatNumber(max);
	}
	if (family === "journal_big") {
		const mb = num(e.journal_mb);
		return mb === null ? "" : t.issues.values.mb(formatNumber(mb));
	}
	if (family === "panel_version_changed" && typeof e.new_version === "string") return e.new_version;
	if (family === "offline") {
		const ago = num(e.last_seen_s_ago);
		return ago === null ? "" : t.issues.values.ago(formatDuration(ago));
	}
	if (family === "ssl_expiry") {
		const days = num(e.days_left);
		const what =
			days === null
				? ""
				: days < 0
					? t.issues.values.expired
					: t.issues.values.days(formatNumber(days));
		return [typeof e.name === "string" ? e.name : "", what].filter(Boolean).join(": ");
	}
	if (family === "quota") {
		const days = num(e.days_left);
		return days === null ? "" : t.issues.values.days(formatNumber(days));
	}
	if (family === "ip_changed") return typeof e.new_ip === "string" ? e.new_ip : "";
	if (family === "ssl_auto_renew_off") {
		const certs = num(e.certs);
		return certs === null ? "" : t.issues.values.certs(formatNumber(certs));
	}
	return "";
}

/** One group per kind of problem, worst first, the biggest group first within a severity. */
export function groupIssues(issues: readonly Issue[]): IssueGroup[] {
	const groups = new Map<string, IssueGroup>();
	for (const issue of issues) {
		const family = familyOf(issue.code);
		const severity = (issue.severity in RANK ? issue.severity : "info") as Severity;
		const known = (t.issues.groups as Record<string, string>)[family];
		let group = groups.get(family);
		if (!group) {
			group = {
				family,
				title: known ?? issue.title,
				severity,
				suggestion: issue.suggestion,
				items: [],
			};
			groups.set(family, group);
		}
		if (RANK[severity] < RANK[group.severity]) group.severity = severity;
		group.items.push({
			id: issue.id,
			serverId: issue.server_id ?? null,
			serverName: issue.server_name ?? "",
			to: family.startsWith("ssl_")
				? "ssl"
				: PANEL_FAMILIES.has(family)
					? "panel"
					: issue.server_id == null
						? null
						: "server",
			value: valueOf(issue),
			recent: issue.recent_24h ?? 0,
		});
	}
	return [...groups.values()].sort(
		(a, b) => RANK[a.severity] - RANK[b.severity] || b.items.length - a.items.length,
	);
}
