import { describe, expect, it } from "vitest";
import type { SslRow } from "@/api/generated/model";
import { DEFAULT_SORT, filterRows, nextSort, sortRows } from "./view";

const row = (over: Partial<SslRow>): SslRow =>
	({
		key: over.name ?? "x",
		kind: "file",
		source: "certbot",
		server_id: 1,
		server_name: "de-1",
		name: "a.example.com",
		domains: ["a.example.com"],
		not_after: 100,
		days_left: 10,
		issuer: null,
		error: null,
		auto_renew: "on",
		renew_failed: false,
		level: "ok",
		checked_at: 1,
		stale: false,
		...over,
	}) as SslRow;

const rows = [
	row({ name: "b.com", not_after: 300, days_left: 30, level: "ok" }),
	row({ name: "a.com", not_after: 100, days_left: -2, level: "critical", server_name: "nl-1" }),
	row({
		name: "c.com",
		not_after: null,
		days_left: null,
		level: "ok",
		server_name: null,
		kind: "probe",
	}),
	row({ name: "d.com", not_after: 200, days_left: 12, level: "warning", auto_renew: "off" }),
];

describe("sorting", () => {
	it("starts with the soonest to expire and flips on a second press of the same column", () => {
		expect(sortRows(rows, DEFAULT_SORT).map((r) => r.name)).toEqual([
			"a.com",
			"d.com",
			"b.com",
			"c.com",
		]);
		const flipped = nextSort(DEFAULT_SORT, "expiry");
		expect(flipped).toEqual({ key: "expiry", direction: "desc" });
		expect(sortRows(rows, flipped).map((r) => r.name)).toEqual([
			"b.com",
			"d.com",
			"a.com",
			"c.com",
		]);
	});
	it("a column pressed for the first time sorts ascending", () => {
		expect(nextSort(DEFAULT_SORT, "name")).toEqual({ key: "name", direction: "asc" });
		expect(sortRows(rows, { key: "name", direction: "asc" }).map((r) => r.name)).toEqual([
			"a.com",
			"b.com",
			"c.com",
			"d.com",
		]);
	});
	it("keeps rows without a value last in both directions", () => {
		for (const direction of ["asc", "desc"] as const) {
			expect(sortRows(rows, { key: "where", direction }).at(-1)?.name).toBe("c.com");
		}
	});
	it("sorts by auto-renew state, the ones that renew first", () => {
		expect(sortRows(rows, { key: "renew", direction: "asc" }).at(-1)?.name).toBe("d.com");
		expect(sortRows(rows, { key: "renew", direction: "desc" })[0].name).toBe("d.com");
	});
});

describe("filtering", () => {
	it("shows only the chosen state", () => {
		expect(filterRows(rows, "critical", "").map((r) => r.name)).toEqual(["a.com"]);
		expect(filterRows(rows, "warning", "").map((r) => r.name)).toEqual(["d.com"]);
		expect(filterRows(rows, "ok", "").map((r) => r.name)).toEqual(["b.com", "c.com"]);
		expect(filterRows(rows, "all", "")).toHaveLength(4);
	});
	it("searches names, domains and servers, ignoring case", () => {
		expect(filterRows(rows, "all", " NL-1 ").map((r) => r.name)).toEqual(["a.com"]);
		expect(filterRows(rows, "all", "B.COM").map((r) => r.name)).toEqual(["b.com"]);
		expect(filterRows(rows, "ok", "nl-1")).toEqual([]);
	});
});
