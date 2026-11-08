import type { IncidentOut, Issue, IssueSummary, ServerOut, SslRow } from "@/api/generated/model";

export type Averages = {
	cpu: number | null;
	ram: number | null;
	cpuCount: number;
	ramCount: number;
};

const mean = (values: number[]) =>
	values.length === 0 ? null : values.reduce((sum, value) => sum + value, 0) / values.length;

const present = (values: (number | null | undefined)[]) =>
	values.filter((value): value is number => typeof value === "number");

/** Average CPU and RAM over the servers that are online and report the figure. */
export function fleetAverages(servers: readonly ServerOut[]): Averages {
	const online = servers.filter((server) => server.status === "online");
	const cpu = present(online.map((server) => server.latest.cpu_pct));
	const ram = present(online.map((server) => server.latest.ram_pct));
	return { cpu: mean(cpu), ram: mean(ram), cpuCount: cpu.length, ramCount: ram.length };
}

export type IssueCounts = { critical: number; warning: number; info: number; total: number };

/** Acknowledged issues are known to the team, so they are not counted. */
export function issueCounts(issues: readonly Issue[]): IssueCounts {
	const open = issues.filter((issue) => !issue.acked);
	const count = (severity: string) => open.filter((issue) => issue.severity === severity).length;
	return {
		critical: count("critical"),
		warning: count("warning"),
		info: count("info"),
		total: open.length,
	};
}

const RANK: Record<string, number> = { critical: 0, warning: 1, info: 2 };

/** When each still-open issue began, from the incident log (the earliest if it has several). */
export function openSince(incidents: readonly IncidentOut[]): Map<string, number> {
	const since = new Map<string, number>();
	for (const incident of incidents) {
		if (incident.closed_at !== null) continue;
		const known = since.get(incident.key);
		if (known === undefined || incident.opened_at < known)
			since.set(incident.key, incident.opened_at);
	}
	return since;
}

/** Worst severity first; within a level the newest, and issues with no known start last. */
export function sortIssues(issues: readonly Issue[], since: ReadonlyMap<string, number>): Issue[] {
	return [...issues].sort(
		(a, b) =>
			(RANK[a.severity] ?? 3) - (RANK[b.severity] ?? 3) ||
			(since.get(b.id) ?? 0) - (since.get(a.id) ?? 0),
	);
}

/** The problems that came back: seen at least twice in the range, the most often first. */
export function recurring(summary: readonly IssueSummary[]): IssueSummary[] {
	return summary
		.filter((row) => row.flapping || row.occurrences >= 2)
		.sort((a, b) => b.occurrences - a.occurrences || b.total_s - a.total_s);
}

export type SortBy = "cpu" | "traffic";

const traffic = (server: ServerOut) => (server.latest.rx_bps ?? 0) + (server.latest.tx_bps ?? 0);

/** The online servers using most CPU or moving most traffic; no figure sorts last. */
export function topServers(servers: readonly ServerOut[], by: SortBy, limit: number): ServerOut[] {
	const value = (server: ServerOut) =>
		by === "cpu" ? (server.latest.cpu_pct ?? -1) : traffic(server);
	return servers
		.filter((server) => server.status === "online")
		.sort((a, b) => value(b) - value(a))
		.slice(0, limit);
}

/** The soonest to expire first; certificates never checked come last. */
export function nearestExpiry(rows: readonly SslRow[], limit: number): SslRow[] {
	return [...rows]
		.sort(
			(a, b) =>
				(a.days_left ?? Number.POSITIVE_INFINITY) - (b.days_left ?? Number.POSITIVE_INFINITY),
		)
		.slice(0, limit);
}

/** Seconds since an epoch-seconds moment. */
export const secondsSince = (epochSeconds: number, now = Date.now()) => now / 1000 - epochSeconds;
