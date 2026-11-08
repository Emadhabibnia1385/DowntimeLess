import type { SslRow } from "@/api/generated/model";

export type SortKey = "name" | "where" | "status" | "expiry" | "renew";
export type SortState = { key: SortKey; direction: "asc" | "desc" };
export type StatusFilter = "all" | "critical" | "warning" | "ok";

/** The soonest to expire first. */
export const DEFAULT_SORT: SortState = { key: "expiry", direction: "asc" };

/** A new column sorts ascending; pressing the same column again flips it. */
export function nextSort(current: SortState, key: SortKey): SortState {
	if (current.key !== key) return { key, direction: "asc" };
	return { key, direction: current.direction === "asc" ? "desc" : "asc" };
}

const RENEW_RANK: Record<string, number> = { on: 0, off: 1, unknown: 2 };

function valueOf(row: SslRow, key: SortKey): number | string | null {
	switch (key) {
		case "name":
			return row.name.toLowerCase();
		case "where":
			return row.server_name ? row.server_name.toLowerCase() : null;
		case "status":
			return row.days_left;
		case "expiry":
			return row.not_after;
		case "renew":
			return RENEW_RANK[row.auto_renew] ?? 3;
	}
}

/** Sorted copy; a row with no value for the column always sits last, whichever way it sorts. */
export function sortRows(rows: readonly SslRow[], sort: SortState): SslRow[] {
	const sign = sort.direction === "asc" ? 1 : -1;
	return [...rows].sort((a, b) => {
		const x = valueOf(a, sort.key);
		const y = valueOf(b, sort.key);
		if (x === null || y === null) return x === y ? 0 : x === null ? 1 : -1;
		const order = typeof x === "string" ? x.localeCompare(y as string) : x - (y as number);
		return order * sign || a.name.localeCompare(b.name);
	});
}

/** Rows of one state ("critical" includes expired) that contain the typed text. */
export function filterRows(rows: readonly SslRow[], status: StatusFilter, query: string): SslRow[] {
	const q = query.trim().toLowerCase();
	return rows.filter((row) => {
		if (status === "critical" && row.level !== "critical") return false;
		if (status === "warning" && row.level !== "warning") return false;
		if (status === "ok" && row.level !== "ok") return false;
		if (!q) return true;
		const text = [row.name, row.server_name ?? "", ...row.domains].join(" ").toLowerCase();
		return text.includes(q);
	});
}
