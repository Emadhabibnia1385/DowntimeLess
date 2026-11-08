import type { ServerHealth } from "@/api/generated/model";

export const BANDS = ["failing", "degraded", "healthy", "unknown"] as const;
export type Band = (typeof BANDS)[number];

export type SortKey = "name" | "score" | "band";
export type SortState = { key: SortKey; direction: "asc" | "desc" } | null;

export function filterHealth(
	rows: readonly ServerHealth[],
	{ query, band }: { query: string; band: Band | "all" },
): ServerHealth[] {
	const needle = query.trim().toLowerCase();
	return rows.filter(
		(row) =>
			(band === "all" || row.band === band) &&
			(needle === "" || row.name.toLowerCase().includes(needle)),
	);
}

/** Ascending, then descending, then back to the master's order (worst first). */
export function nextSort(sort: SortState, key: SortKey): SortState {
	if (sort?.key !== key) return { key, direction: "asc" };
	return sort.direction === "asc" ? { key, direction: "desc" } : null;
}

const bandRank = (row: ServerHealth) => BANDS.indexOf(row.band as Band);

export function sortHealth(rows: readonly ServerHealth[], sort: SortState): ServerHealth[] {
	if (!sort) return [...rows];
	const sign = sort.direction === "asc" ? 1 : -1;
	const value = (row: ServerHealth): number | string =>
		sort.key === "name" ? row.name : sort.key === "band" ? bandRank(row) : (row.score ?? 101);
	return [...rows].sort((a, b) => {
		const x = value(a);
		const y = value(b);
		const order = typeof x === "string" ? x.localeCompare(String(y)) : Number(x) - Number(y);
		return sign * order || a.name.localeCompare(b.name);
	});
}

export function bandTone(band: string): "success" | "warning" | "danger" | "neutral" {
	if (band === "healthy") return "success";
	if (band === "degraded") return "warning";
	if (band === "failing") return "danger";
	return "neutral";
}
