import type { IncidentOut, IssueSummary } from "@/api/generated/model";
import { t } from "@/strings";
import { familyOf } from "./group";

export type SortKey = "occurrences" | "total" | "last";
export type SortState = { key: SortKey; direction: "asc" | "desc" } | null;

/** The timeline shows this many of the newest occurrences. */
export const TIMELINE_LIMIT = 100;

const TONES = { critical: "danger", warning: "warning", info: "info" } as const;

export const severityTone = (severity: string) =>
	TONES[severity as keyof typeof TONES] ?? "neutral";

const RANK: Record<string, number> = { critical: 0, warning: 1, info: 2 };
export const SEVERITY_FILTERS = ["critical", "warning", "info"] as const;

// Certificate and link problems carry names in their own title; the rest use the shared label.
const OWN_TITLE = new Set(["ssl_expiry", "ping"]);

/** A short label: the shared one per kind, or the issue's own title when that holds the detail. */
export function issueLabel(code: string | null, title: string | null): string {
	const family = code ? familyOf(code) : "";
	const known = (t.issues.groups as Record<string, string>)[family];
	if (known && !OWN_TITLE.has(family)) return known;
	return title ?? known ?? code ?? "";
}

export type SummaryFilter = { query: string; severity: string };

export function filterSummary(
	rows: readonly IssueSummary[],
	filter: SummaryFilter,
): IssueSummary[] {
	const query = filter.query.trim().toLowerCase();
	return rows.filter((row) => {
		if (filter.severity !== "all" && row.severity !== filter.severity) return false;
		if (!query) return true;
		const haystack = [row.server_name, row.title, issueLabel(row.code, row.title), row.key]
			.filter(Boolean)
			.join(" ")
			.toLowerCase();
		return haystack.includes(query);
	});
}

const VALUE: Record<SortKey, (row: IssueSummary) => number> = {
	occurrences: (row) => row.occurrences,
	total: (row) => row.total_s,
	last: (row) => row.last_at,
};

/** The master's order (most occurrences, then worst) unless a column is chosen. */
export function sortSummary(rows: readonly IssueSummary[], sort: SortState): IssueSummary[] {
	if (!sort) return [...rows];
	const sign = sort.direction === "asc" ? 1 : -1;
	return [...rows].sort(
		(a, b) =>
			sign * (VALUE[sort.key](a) - VALUE[sort.key](b)) ||
			(RANK[a.severity] ?? 3) - (RANK[b.severity] ?? 3),
	);
}

/** First press sorts high to low, the second reverses it, the third restores the default. */
export function nextSort(current: SortState, key: SortKey): SortState {
	if (current?.key !== key) return { key, direction: "desc" };
	return current.direction === "desc" ? { key, direction: "asc" } : null;
}

export function newestIncidents(incidents: readonly IncidentOut[]): IncidentOut[] {
	return [...incidents].sort((a, b) => b.opened_at - a.opened_at).slice(0, TIMELINE_LIMIT);
}
