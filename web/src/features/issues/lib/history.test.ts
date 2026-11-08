import { describe, expect, it } from "vitest";
import type { IncidentOut, IssueSummary } from "@/api/generated/model";
import { filterSummary, issueLabel, nextSort, newestIncidents, sortSummary } from "./history";
import { isHistoryRange, isIssuesTab } from "./tabs";

const row = (over: Partial<IssueSummary>): IssueSummary => ({
	key: "server:1:disk",
	code: "disk",
	server_id: 1,
	server_name: "de-1",
	title: "دیسک رو به پر شدن است",
	severity: "warning",
	occurrences: 1,
	total_s: 60,
	last_at: 100,
	active_now: false,
	flapping: false,
	evidence: {},
	...over,
});

describe("tabs", () => {
	it("accepts only known tabs and ranges", () => {
		expect(isIssuesTab("history")).toBe(true);
		expect(isIssuesTab("old")).toBe(false);
		expect(isHistoryRange("7d")).toBe(true);
		expect(isHistoryRange("1h")).toBe(false);
	});
});

describe("issueLabel", () => {
	it("uses the shared label, but the own title for certificates and links", () => {
		expect(issueLabel("disk", "x")).toBe("دیسک رو به پر شدن");
		expect(issueLabel("ssl_expiry", "گواهی a.com")).toBe("گواهی a.com");
		expect(issueLabel("ping:1.2.3.4", "اتصال به x")).toBe("اتصال به x");
		expect(issueLabel("odd", "عنوان")).toBe("عنوان");
	});
});

describe("filterSummary", () => {
	const rows = [
		row({}),
		row({ key: "k2", code: "cpu", server_name: "ir-2", severity: "critical" }),
	];
	it("filters by severity and by text on the server or the issue", () => {
		expect(filterSummary(rows, { query: "", severity: "all" })).toHaveLength(2);
		expect(filterSummary(rows, { query: "", severity: "critical" }).map((r) => r.key)).toEqual([
			"k2",
		]);
		expect(filterSummary(rows, { query: " IR-2 ", severity: "all" })).toHaveLength(1);
		expect(filterSummary(rows, { query: "دیسک", severity: "all" })).toHaveLength(2);
		expect(filterSummary(rows, { query: "zzz", severity: "all" })).toHaveLength(0);
	});
});

describe("sortSummary", () => {
	const rows = [
		row({ key: "a", occurrences: 2, total_s: 10, last_at: 5 }),
		row({ key: "b", occurrences: 9, total_s: 5, last_at: 50 }),
		row({ key: "c", occurrences: 4, total_s: 99, last_at: 20 }),
	];
	it("keeps the master order by default and sorts a chosen column both ways", () => {
		expect(sortSummary(rows, null).map((r) => r.key)).toEqual(["a", "b", "c"]);
		expect(sortSummary(rows, { key: "occurrences", direction: "desc" }).map((r) => r.key)).toEqual([
			"b",
			"c",
			"a",
		]);
		expect(sortSummary(rows, { key: "total", direction: "asc" }).map((r) => r.key)).toEqual([
			"b",
			"a",
			"c",
		]);
	});
	it("cycles high to low, low to high, then back to the default", () => {
		const first = nextSort(null, "last");
		expect(first).toEqual({ key: "last", direction: "desc" });
		const second = nextSort(first, "last");
		expect(second).toEqual({ key: "last", direction: "asc" });
		expect(nextSort(second, "last")).toBeNull();
		expect(nextSort(second, "total")).toEqual({ key: "total", direction: "desc" });
	});
});

describe("newestIncidents", () => {
	it("keeps the newest hundred", () => {
		const incidents: IncidentOut[] = Array.from({ length: 130 }, (_, id) => ({
			id,
			key: "k",
			code: "disk",
			server_id: 1,
			server_name: "de-1",
			severity: "warning",
			title: "t",
			opened_at: id,
			closed_at: id + 1,
			duration_s: 1,
		}));
		const out = newestIncidents(incidents);
		expect(out).toHaveLength(100);
		expect(out[0].opened_at).toBe(129);
	});
});
