import type { ServerTraffic } from "@/api/generated/model";

export type SortKey =
	| "name"
	| "role"
	| "today"
	| "yesterday"
	| "total"
	| "rx"
	| "tx"
	| "avg"
	| "peak"
	| "share";
export type SortDirection = "asc" | "desc";
export type SortState = { key: SortKey; direction: SortDirection } | null;

/** The name people use for a server: its alias when it has one. */
export const serverLabel = (row: ServerTraffic): string => row.alias || row.name;

const value = (row: ServerTraffic, key: SortKey): number | string => {
	switch (key) {
		case "name":
			return serverLabel(row);
		case "role":
			return row.role;
		case "today":
			return row.today.total;
		case "yesterday":
			return row.yesterday.total;
		case "total":
			return row.period.total;
		case "rx":
			return row.period.rx;
		case "tx":
			return row.period.tx;
		case "avg":
			return row.avg_per_day.total;
		case "peak":
			return row.peak_day?.total ?? 0;
		case "share":
			return row.share_pct;
	}
};

/** Rows by one column; with no sort chosen, the busiest server first. */
export function sortRows(rows: readonly ServerTraffic[], sort: SortState): ServerTraffic[] {
	const { key, direction } = sort ?? { key: "total" as const, direction: "desc" as const };
	const sign = direction === "asc" ? 1 : -1;
	return [...rows].sort((a, b) => {
		const left = value(a, key);
		const right = value(b, key);
		const order =
			typeof left === "string" && typeof right === "string"
				? left.localeCompare(right)
				: Number(left) - Number(right);
		return order * sign || serverLabel(a).localeCompare(serverLabel(b));
	});
}

/** The next sort after pressing a column: a new column starts in `first`, the same one flips. */
export function nextSort(current: SortState, key: SortKey, first: SortDirection): SortState {
	if (current?.key !== key) return { key, direction: first };
	return { key, direction: current.direction === "asc" ? "desc" : "asc" };
}

/** Rows whose name, alias or role matches the text and the chosen role ("" for any role). */
export function filterRows(
	rows: readonly ServerTraffic[],
	text: string,
	role: string,
): ServerTraffic[] {
	const needle = text.trim().toLowerCase();
	return rows.filter(
		(row) =>
			(role === "" || row.role === role) &&
			(needle === "" ||
				row.name.toLowerCase().includes(needle) ||
				(row.alias ?? "").toLowerCase().includes(needle)),
	);
}
