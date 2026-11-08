import { describe, expect, it } from "vitest";
import type { ServerHealth } from "@/api/generated/model";
import { bandTone, filterHealth, nextSort, sortHealth } from "./health";

const row = (over: Partial<ServerHealth>): ServerHealth => ({
	server_id: 1,
	name: "de-1",
	role: "exit",
	country: "DE",
	category_id: null,
	status: "online",
	variant: "exit",
	score: 90,
	band: "healthy",
	gates: [],
	penalties: [],
	open_issues: 0,
	not_measured: [],
	...over,
});

const rows = [
	row({ server_id: 1, name: "de-1", score: 90, band: "healthy" }),
	row({ server_id: 2, name: "ir-2", score: 40, band: "failing" }),
	row({ server_id: 3, name: "ir-3", score: 72, band: "degraded" }),
	row({ server_id: 4, name: "new-1", score: null, band: "unknown" }),
];

describe("health table helpers", () => {
	it("filters by band and by name", () => {
		expect(filterHealth(rows, { query: "", band: "failing" }).map((r) => r.name)).toEqual(["ir-2"]);
		expect(filterHealth(rows, { query: " IR-", band: "all" }).map((r) => r.name)).toEqual([
			"ir-2",
			"ir-3",
		]);
		expect(filterHealth(rows, { query: "zz", band: "all" })).toEqual([]);
	});

	it("sorts by score with unscored servers last, then back to the master's order", () => {
		const asc = sortHealth(rows, { key: "score", direction: "asc" }).map((r) => r.name);
		expect(asc).toEqual(["ir-2", "ir-3", "de-1", "new-1"]);
		const desc = sortHealth(rows, { key: "score", direction: "desc" }).map((r) => r.name);
		expect(desc[0]).toBe("new-1");
		expect(sortHealth(rows, null).map((r) => r.name)).toEqual(rows.map((r) => r.name));
	});

	it("sorts by name and by band", () => {
		expect(sortHealth(rows, { key: "name", direction: "desc" })[0]?.name).toBe("new-1");
		expect(sortHealth(rows, { key: "band", direction: "asc" })[0]?.band).toBe("failing");
	});

	it("cycles ascending, descending, off", () => {
		const first = nextSort(null, "score");
		expect(first).toEqual({ key: "score", direction: "asc" });
		const second = nextSort(first, "score");
		expect(second).toEqual({ key: "score", direction: "desc" });
		expect(nextSort(second, "score")).toBeNull();
		expect(nextSort(second, "name")).toEqual({ key: "name", direction: "asc" });
	});

	it("maps bands to tones", () => {
		expect([
			bandTone("healthy"),
			bandTone("degraded"),
			bandTone("failing"),
			bandTone("unknown"),
		]).toEqual(["success", "warning", "danger", "neutral"]);
	});
});
