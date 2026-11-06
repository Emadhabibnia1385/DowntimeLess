import type { PingCell } from "@/api/generated/model";

export type Health = "ok" | "degraded" | "down" | "unknown";

export type Thresholds = { loss_warn: number; loss_crit: number };

export type Matrix = {
	rows: { id: number; name: string }[];
	columns: { key: string; name: string; target: string }[];
	/** The cell for a row id and a column key, if that pair was measured. */
	cell: (rowId: number, columnKey: string) => PingCell | undefined;
};

// The schema leaves these fields untyped, so a number is checked for.
export const numberOrNull = (value: unknown): number | null =>
	typeof value === "number" ? value : null;

/** The state of one link from its packet loss and the alert thresholds. */
export function healthOf(loss: number | null, limits: Thresholds): Health {
	if (loss === null) return "unknown";
	if (loss >= limits.loss_crit) return "down";
	if (loss >= limits.loss_warn) return "degraded";
	return "ok";
}

/** Lays the measured links out as sources (rows) by destinations (columns). */
export function buildMatrix(cells: readonly PingCell[]): Matrix {
	const rows = new Map<number, string>();
	const columns = new Map<string, { name: string; target: string }>();
	const byPair = new Map<string, PingCell>();
	for (const cell of cells) {
		rows.set(cell.from_id, cell.from_name);
		const key = typeof cell.to_id === "number" ? `id:${cell.to_id}` : cell.target;
		columns.set(key, { name: cell.to_name, target: cell.target });
		byPair.set(`${cell.from_id}|${key}`, cell);
	}
	return {
		rows: [...rows]
			.map(([id, name]) => ({ id, name }))
			.sort((a, b) => a.name.localeCompare(b.name)),
		columns: [...columns]
			.map(([key, value]) => ({ key, ...value }))
			.sort((a, b) => a.name.localeCompare(b.name)),
		cell: (rowId, columnKey) => byPair.get(`${rowId}|${columnKey}`),
	};
}
