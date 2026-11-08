import type { PanelNode, Reseller } from "@/api/generated/model";

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

export function nodeTone(node: PanelNode): Tone {
	if (!node.enabled || node.ignored) return "neutral";
	if (node.status !== "connected") return "danger";
	return node.dropped ? "warning" : "success";
}

/** Last hour against the node's own median: the lower of users and bytes (the one that alerts). */
export function shareOf(node: PanelNode): number | null {
	const parts = [node.users_pct, node.bytes_pct].filter((v): v is number => typeof v === "number");
	return parts.length ? Math.min(...parts) : null;
}

export function shareTone(share: number | null, dropAt: number): Tone {
	if (share === null) return "neutral";
	if (share < dropAt / 2) return "danger";
	return share < dropAt ? "warning" : "success";
}

export const levelTone = (level: string): Tone =>
	level === "critical" ? "danger" : level === "warning" ? "warning" : "success";

export type ResellerKey = "name" | "used" | "limit" | "percent" | "hours";
export type ResellerSort = { key: ResellerKey; direction: "asc" | "desc" };

/** The fullest first: that is who the owner has to call. */
export const DEFAULT_RESELLER_SORT: ResellerSort = { key: "percent", direction: "desc" };

export function nextSort(current: ResellerSort, key: ResellerKey): ResellerSort {
	if (current.key !== key)
		return { key, direction: key === "name" || key === "hours" ? "asc" : "desc" };
	return { key, direction: current.direction === "asc" ? "desc" : "asc" };
}

function value(row: Reseller, key: ResellerKey): number | string | null {
	switch (key) {
		case "name":
			return row.name.toLowerCase();
		case "used":
			return row.used;
		case "limit":
			return row.limit;
		case "percent":
			return row.used_pct;
		case "hours":
			return row.hours_left ?? null;
	}
}

/** Sorted copy; a reseller with no burn (no hours left figure) always sits last. */
export function sortResellers(rows: readonly Reseller[], sort: ResellerSort): Reseller[] {
	const sign = sort.direction === "asc" ? 1 : -1;
	return [...rows].sort((a, b) => {
		const x = value(a, sort.key);
		const y = value(b, sort.key);
		if (x === null || y === null) return x === y ? 0 : x === null ? 1 : -1;
		const order = typeof x === "string" ? x.localeCompare(String(y)) : x - (y as number);
		return order * sign || a.name.localeCompare(b.name);
	});
}

export const USER_STATUSES = [
	"active",
	"limited",
	"expired",
	"on_hold",
	"disabled",
	"other",
] as const;
