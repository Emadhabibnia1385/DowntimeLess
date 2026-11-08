import type { ServerOut } from "@/api/generated/model";

export type SortKey =
	| "name"
	| "role"
	| "status"
	| "cpu"
	| "ram"
	| "disk"
	| "steal"
	| "download"
	| "upload"
	| "bandwidth";
export type SortDirection = "asc" | "desc";
export type SortState = { key: SortKey; direction: SortDirection } | null;

const STATUS_ORDER: Record<string, number> = { online: 0, offline: 1, pending: 2 };

const value = (server: ServerOut, key: SortKey): number | string | null | undefined => {
	switch (key) {
		case "name":
			return server.name;
		case "role":
			return server.role;
		case "status":
			return STATUS_ORDER[server.status] ?? 3;
		case "cpu":
			return server.latest.cpu_pct;
		case "ram":
			return server.latest.ram_pct;
		case "disk":
			return server.latest.disk_pct;
		case "steal":
			return server.latest.steal_pct;
		case "download":
			return server.latest.rx_bps;
		case "upload":
			return server.latest.tx_bps;
		case "bandwidth":
			return server.latest.rx_bps == null && server.latest.tx_bps == null
				? null
				: (server.latest.rx_bps ?? 0) + (server.latest.tx_bps ?? 0);
	}
};

/** Servers ordered by one column; a server with no value yet goes last whichever way it runs. */
export function sortServers(servers: readonly ServerOut[], sort: SortState): ServerOut[] {
	if (!sort) return [...servers];
	const sign = sort.direction === "asc" ? 1 : -1;
	return [...servers].sort((a, b) => {
		const x = value(a, sort.key);
		const y = value(b, sort.key);
		if (x == null && y == null) return 0;
		if (x == null) return 1;
		if (y == null) return -1;
		if (typeof x === "string" || typeof y === "string") {
			return sign * String(x).localeCompare(String(y), "fa");
		}
		return sign * (x - y);
	});
}

/** Click order of a header: ascending, then descending, then back to the default order. */
export function nextSort(current: SortState, key: SortKey, first: SortDirection): SortState {
	if (current?.key !== key) return { key, direction: first };
	if (current.direction === first) return { key, direction: first === "asc" ? "desc" : "asc" };
	return null;
}
