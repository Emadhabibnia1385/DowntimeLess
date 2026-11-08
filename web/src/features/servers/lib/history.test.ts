import { describe, expect, it } from "vitest";
import type { MetricPoint } from "@/api/generated/model";
import { buildHistory } from "./history";

const point = (ts: number, over: Partial<MetricPoint> = {}): MetricPoint => ({
	ts,
	cpu: 10,
	ram_pct: 40,
	disk_pct: 50,
	rx_bps: 2_000_000,
	tx_bps: 500_000,
	rx_bytes: 1000,
	tx_bytes: 400,
	...over,
});

const points = [point(120), point(60, { cpu: null }), point(180, { swap_pct: 5, load1: 0.5 })];

describe("buildHistory", () => {
	it("sorts the points oldest first and keeps one value per time", () => {
		const { times, charts } = buildHistory("usage", points);
		expect(times).toEqual([60, 120, 180]);
		expect(charts[0]?.series.find((s) => s.key === "cpu")?.values).toEqual([null, 10, 10]);
	});

	it("leaves out a series nobody reported", () => {
		const keys = buildHistory("usage", points).charts[0]?.series.map((s) => s.key);
		expect(keys).toEqual(["cpu", "ram", "disk", "swap"]);
		const old = buildHistory("usage", [point(1)]).charts[0]?.series.map((s) => s.key);
		expect(old).toEqual(["cpu", "ram", "disk"]);
	});

	it("draws usage on a fixed 0 to 100 scale", () => {
		expect(buildHistory("usage", points).charts[0]?.domain).toEqual([0, 100]);
	});

	it("shows network speed in megabits and the volume as a second chart", () => {
		const { charts } = buildHistory("network", points);
		expect(charts.map((c) => c.key)).toEqual(["speed", "volume"]);
		expect(charts[0]?.series[0]?.values[0]).toBe(2);
		expect(charts[0]?.series[1]?.values[0]).toBe(0.5);
		expect(charts[1]?.series[0]?.values[0]).toBe(1000);
	});

	it("names the core count in the load description only when known", () => {
		expect(buildHistory("load", points, 4).description).toContain("۴");
		expect(buildHistory("load", points, null).description).not.toContain("هسته دارد");
	});

	it("has no chart lines when the agent sent nothing for a tab", () => {
		expect(buildHistory("quality", points).charts[0]?.series).toEqual([]);
		expect(buildHistory("conns", []).times).toEqual([]);
	});
});
