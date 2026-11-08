import { describe, expect, it } from "vitest";
import type { IncidentOut, Issue, IssueSummary, ServerOut, SslRow } from "@/api/generated/model";
import {
	fleetAverages,
	issueCounts,
	nearestExpiry,
	openSince,
	recurring,
	sortIssues,
	topServers,
} from "./stats";

const server = (id: number, status: string, latest: ServerOut["latest"]) =>
	({ id, name: `s-${id}`, alias: "", status, latest }) as ServerOut;

const issue = (id: string, severity: string) => ({ id, severity }) as Issue;

describe("fleetAverages", () => {
	it("averages only online servers that report the figure", () => {
		const average = fleetAverages([
			server(1, "online", { cpu_pct: 10, ram_pct: 40 }),
			server(2, "online", { cpu_pct: 30 }),
			server(3, "offline", { cpu_pct: 99, ram_pct: 99 }),
		]);
		expect(average).toEqual({ cpu: 20, ram: 40, cpuCount: 2, ramCount: 1 });
	});

	it("has no average when nothing is online", () => {
		expect(fleetAverages([server(1, "offline", { cpu_pct: 5 })]).cpu).toBeNull();
	});
});

describe("issues", () => {
	it("counts by severity", () => {
		const counts = issueCounts([issue("a", "info"), issue("b", "critical"), issue("c", "info")]);
		expect(counts).toEqual({ critical: 1, warning: 0, info: 2, total: 3 });
	});

	it("does not count acknowledged issues", () => {
		const known = { ...issue("d", "critical"), acked: true } as Issue;
		const counts = issueCounts([issue("a", "warning"), known]);
		expect(counts).toEqual({ critical: 0, warning: 1, info: 0, total: 1 });
	});

	it("takes the earliest start of an open incident and ignores closed ones", () => {
		const since = openSince([
			{ key: "a", opened_at: 50, closed_at: null },
			{ key: "a", opened_at: 20, closed_at: null },
			{ key: "b", opened_at: 5, closed_at: 9 },
		] as IncidentOut[]);
		expect([...since]).toEqual([["a", 20]]);
	});

	it("sorts worst first, then newest, unknown starts last", () => {
		const sorted = sortIssues(
			[
				issue("w-old", "warning"),
				issue("w-new", "warning"),
				issue("c", "critical"),
				issue("w-?", "warning"),
			],
			new Map([
				["w-old", 10],
				["w-new", 90],
			]),
		);
		expect(sorted.map((item) => item.id)).toEqual(["c", "w-new", "w-old", "w-?"]);
	});

	it("keeps only what came back, the most often first", () => {
		const rows = recurring([
			{ key: "a", occurrences: 1, flapping: false, total_s: 1 },
			{ key: "b", occurrences: 3, flapping: false, total_s: 1 },
			{ key: "c", occurrences: 5, flapping: true, total_s: 1 },
		] as IssueSummary[]);
		expect(rows.map((row) => row.key)).toEqual(["c", "b"]);
	});
});

describe("topServers", () => {
	const fleet = [
		server(1, "online", { cpu_pct: 10, rx_bps: 900, tx_bps: 100 }),
		server(2, "online", { cpu_pct: 70, rx_bps: 10 }),
		server(3, "online", {}),
		server(4, "offline", { cpu_pct: 99 }),
	];

	it("ranks by CPU and leaves out offline servers", () => {
		expect(topServers(fleet, "cpu", 8).map((item) => item.id)).toEqual([2, 1, 3]);
	});

	it("ranks by download plus upload and cuts to the limit", () => {
		expect(topServers(fleet, "traffic", 2).map((item) => item.id)).toEqual([1, 2]);
	});
});

describe("nearestExpiry", () => {
	it("puts the soonest first and the unchecked last", () => {
		const rows = nearestExpiry(
			[
				{ key: "a", days_left: 40 },
				{ key: "b", days_left: null },
				{ key: "c", days_left: -2 },
			] as SslRow[],
			2,
		);
		expect(rows.map((row) => row.key)).toEqual(["c", "a"]);
	});
});
