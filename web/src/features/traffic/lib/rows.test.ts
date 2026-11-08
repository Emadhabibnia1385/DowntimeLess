import { describe, expect, it } from "vitest";
import type { ServerTraffic } from "@/api/generated/model";
import { filterRows, nextSort, sortRows } from "./rows";

const vol = (total: number) => ({ rx: total * 0.8, tx: total * 0.2, total });

const row = (id: number, name: string, role: string, total: number): ServerTraffic => ({
	server_id: id,
	name,
	alias: null,
	role,
	country: "DE",
	category_id: null,
	today: vol(total / 10),
	yesterday: vol(total / 5),
	period: vol(total),
	avg_per_day: vol(total / 30),
	active_days: 30,
	peak_day: total ? { date: "2026-11-01", ...vol(total / 3) } : null,
	share_pct: total / 10,
});

const rows = [row(1, "de-1", "exit", 300), row(2, "ir-1", "relay", 900), row(3, "nl-1", "exit", 0)];

describe("traffic rows", () => {
	it("puts the busiest server first when nothing is chosen", () => {
		expect(sortRows(rows, null).map((r) => r.name)).toEqual(["ir-1", "de-1", "nl-1"]);
	});

	it("sorts by a column either way and breaks ties by name", () => {
		expect(sortRows(rows, { key: "total", direction: "asc" }).map((r) => r.name)).toEqual([
			"nl-1",
			"de-1",
			"ir-1",
		]);
		expect(sortRows(rows, { key: "name", direction: "desc" }).map((r) => r.name)).toEqual([
			"nl-1",
			"ir-1",
			"de-1",
		]);
		expect(sortRows(rows, { key: "peak", direction: "desc" })[0]?.name).toBe("ir-1");
		expect(sortRows(rows, { key: "role", direction: "asc" })[0]?.role).toBe("exit");
	});

	it("flips a column on the second press", () => {
		const first = nextSort(null, "total", "desc");
		expect(first).toEqual({ key: "total", direction: "desc" });
		expect(nextSort(first, "total", "desc")).toEqual({ key: "total", direction: "asc" });
		expect(nextSort(first, "name", "asc")).toEqual({ key: "name", direction: "asc" });
	});

	it("filters by text and by role", () => {
		expect(filterRows(rows, "DE", "").map((r) => r.name)).toEqual(["de-1"]);
		expect(filterRows(rows, "", "exit")).toHaveLength(2);
		expect(filterRows(rows, "nl", "relay")).toHaveLength(0);
		expect(filterRows([{ ...row(4, "x", "exit", 1), alias: "Tokyo" }], "tok", "")).toHaveLength(1);
	});
});
