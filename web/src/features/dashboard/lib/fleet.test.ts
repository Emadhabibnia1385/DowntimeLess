import { describe, expect, it } from "vitest";
import type { FleetPoint } from "@/api/generated/model";
import { buildFleet } from "./fleet";

const point = (ts: number, over: Partial<FleetPoint> = {}): FleetPoint => ({
	ts,
	rx_bytes: 37_500_000,
	tx_bytes: 0,
	cpu: 10,
	ram_pct: 20,
	disk_pct: null,
	servers: 3,
	...over,
});

describe("buildFleet", () => {
	it("turns bytes per point into megabits per second and sorts by time", () => {
		const fleet = buildFleet("traffic", [point(600), point(300)], "24h");
		expect(fleet.times).toEqual([300, 600]);
		const speed = fleet.charts[0].series.find((series) => series.key === "rx");
		// 37.5 MB over a 300 s bucket is 1 Mbit/s.
		expect(speed?.values).toEqual([1, 1]);
		const volume = fleet.charts[1].series.find((series) => series.key === "rx");
		expect(volume?.values).toEqual([37_500_000, 37_500_000]);
	});

	it("leaves out a series nobody reported", () => {
		const usage = buildFleet("usage", [point(1)], "6h").charts[0].series;
		expect(usage.map((series) => series.key)).toEqual(["cpu", "ram"]);
	});

	it("counts the servers reporting", () => {
		const fleet = buildFleet("servers", [point(1, { servers: 2 })], "7d");
		expect(fleet.charts[0].series[0].values).toEqual([2]);
	});
});
