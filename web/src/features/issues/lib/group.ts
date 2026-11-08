import type { Issue } from "@/api/generated/model";
import { formatDuration, formatNumber, formatPercent, t } from "@/strings";

export type Severity = "critical" | "warning" | "info";
export type GroupItem = {
	id: string;
	serverId: number | null;
	serverName: string;
	to: "server" | "ssl" | null;
	value: string;
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
];

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
	if (Array.isArray(e.units)) return e.units.join(", ");
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
			to: family.startsWith("ssl_") ? "ssl" : issue.server_id == null ? null : "server",
			value: valueOf(issue),
		});
	}
	return [...groups.values()].sort(
		(a, b) => RANK[a.severity] - RANK[b.severity] || b.items.length - a.items.length,
	);
}
