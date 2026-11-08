import type { PingCell } from "@/api/generated/model";

export type Health = "ok" | "degraded" | "down" | "unknown";

export type Thresholds = { loss_warn: number; loss_crit: number };

export type Matrix = {
	/** Foreign servers, down the side. */
	rows: { id: number; name: string; target: string }[];
	/** Iran relays, along the top. */
	columns: { key: string; name: string }[];
	/** The ping from the column's Iran relay to the row's foreign server, if measured. */
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

/** Lays the Iran-to-foreign pings out as foreign servers (rows) by Iran relays (columns). */
export function buildMatrix(cells: readonly PingCell[]): Matrix {
	const rows = new Map<number, { name: string; target: string }>();
	const columns = new Map<string, string>();
	const byPair = new Map<string, PingCell>();
	for (const cell of cells) {
		if (typeof cell.to_id !== "number") continue;
		rows.set(cell.to_id, { name: cell.to_name, target: cell.target });
		const key = `id:${cell.from_id}`;
		columns.set(key, cell.from_name);
		byPair.set(`${cell.to_id}|${key}`, cell);
	}
	return {
		rows: [...rows]
			.map(([id, value]) => ({ id, ...value }))
			.sort((a, b) => a.name.localeCompare(b.name)),
		columns: [...columns]
			.map(([key, name]) => ({ key, name }))
			.sort((a, b) => a.name.localeCompare(b.name)),
		cell: (rowId, columnKey) => byPair.get(`${rowId}|${columnKey}`),
	};
}
