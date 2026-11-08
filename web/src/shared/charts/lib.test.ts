import { describe, expect, it } from "vitest";
import {
	areaPath,
	csvBlob,
	csvNumber,
	csvTime,
	gapLimit,
	linePath,
	makeXScale,
	nearestIndex,
	niceDomain,
	niceStep,
	splitSegments,
	toCsv,
} from "./lib";

describe("niceStep", () => {
	it("picks 1, 2, 2.5 or 5 times a power of ten", () => {
		expect(niceStep(100, 5)).toBe(20);
		expect(niceStep(100, 4)).toBe(25);
		expect(niceStep(7, 4)).toBe(2);
		expect(niceStep(0.9, 3)).toBe(0.5);
		expect(niceStep(4200, 4)).toBe(2000);
	});
	it("falls back to 1 for an empty span", () => {
		expect(niceStep(0, 4)).toBe(1);
	});
});

describe("niceDomain", () => {
	it("keeps a fixed domain and ticks it evenly", () => {
		const domain = niceDomain([5, 20], [0, 100], 5);
		expect([domain.min, domain.max]).toEqual([0, 100]);
		expect(domain.ticks).toEqual([0, 20, 40, 60, 80, 100]);
	});
	it("starts at zero and ends on a round tick above the data", () => {
		const domain = niceDomain([3, 47, null, 12]);
		expect(domain.min).toBe(0);
		expect(domain.max).toBeGreaterThanOrEqual(47);
		expect(domain.ticks[0]).toBe(0);
		expect(domain.ticks.at(-1)).toBe(domain.max);
	});
	it("gives all-zero or empty data a usable range", () => {
		expect(niceDomain([0, 0]).max).toBe(1);
		expect(niceDomain([]).max).toBe(1);
		expect(niceDomain([null]).ticks.length).toBeGreaterThan(1);
	});
	it("avoids floating point noise in ticks", () => {
		const { ticks } = niceDomain([0, 0.3], undefined, 3);
		expect(ticks).toEqual([0, 0.1, 0.2, 0.3]);
	});
});

describe("makeXScale", () => {
	it("maps time left to right, or newest at the left when reversed", () => {
		const plain = makeXScale(100, 200, 10, 300, false);
		expect(plain.x(100)).toBe(10);
		expect(plain.x(200)).toBe(310);
		const reversed = makeXScale(100, 200, 10, 300, true);
		expect(reversed.x(200)).toBe(10);
		expect(reversed.x(100)).toBe(310);
	});
	it("inverts and clamps", () => {
		const scale = makeXScale(100, 200, 10, 300, true);
		expect(scale.time(160)).toBe(150);
		expect(scale.time(-50)).toBe(200);
		expect(scale.time(9999)).toBe(100);
	});
	it("centres a single instant", () => {
		expect(makeXScale(5, 5, 0, 100, false).x(5)).toBe(50);
	});
});

describe("nearestIndex", () => {
	const times = [10, 20, 40, 80];
	it("finds the closest time", () => {
		expect(nearestIndex(times, 11)).toBe(0);
		expect(nearestIndex(times, 31)).toBe(2);
		expect(nearestIndex(times, 59)).toBe(2);
		expect(nearestIndex(times, 61)).toBe(3);
		expect(nearestIndex(times, 1000)).toBe(3);
		expect(nearestIndex(times, -5)).toBe(0);
	});
	it("is -1 for no times", () => {
		expect(nearestIndex([], 5)).toBe(-1);
	});
	it("takes the earlier one on a tie", () => {
		expect(nearestIndex([10, 20], 15)).toBe(0);
	});
});

describe("splitSegments", () => {
	const times = [0, 30, 60, 90, 120, 150];
	it("breaks the line at null values", () => {
		expect(splitSegments(times, [1, 2, null, 4, 5, 6])).toEqual([
			[0, 1],
			[3, 4, 5],
		]);
	});
	it("keeps a lone point as its own run and drops all-null series", () => {
		expect(splitSegments(times, [null, 2, null, null, null, null])).toEqual([[1]]);
		expect(splitSegments(times, [null, null, null, null, null, null])).toEqual([]);
	});
	it("breaks at a hole in time longer than the limit", () => {
		expect(splitSegments([0, 30, 60, 600, 630], [1, 1, 1, 1, 1], 100)).toEqual([
			[0, 1, 2],
			[3, 4],
		]);
	});
});

describe("gapLimit", () => {
	it("is 3.5 times the usual step", () => {
		expect(gapLimit([0, 30, 60, 90, 120])).toBe(105);
	});
	it("does not guess from fewer than three steps", () => {
		expect(gapLimit([0, 30, 60])).toBe(Number.POSITIVE_INFINITY);
	});
});

describe("paths", () => {
	const points = [
		{ x: 0, y: 10 },
		{ x: 5.55, y: 20 },
	];
	it("draws a line and a closed area", () => {
		expect(linePath(points)).toBe("M0.0 10.0L5.5 20.0");
		expect(areaPath(points, 30)).toBe("M0.0 10.0L5.5 20.0L5.5 30.0L0.0 30.0Z");
	});
	it("is empty for no points", () => {
		expect(areaPath([], 30)).toBe("");
	});
});

describe("CSV", () => {
	it("writes Latin digits with a dot and nothing for gaps", () => {
		expect(csvNumber(12.34567)).toBe("12.346");
		expect(csvNumber(3)).toBe("3");
		expect(
			toCsv(
				["time", "cpu"],
				[
					["2026-11-08 10:00:00", 12.5],
					["2026-11-08 10:05:00", null],
				],
			),
		).toBe("time,cpu\r\n2026-11-08 10:00:00,12.5\r\n2026-11-08 10:05:00,");
	});
	it("quotes cells that hold commas, quotes or new lines", () => {
		expect(toCsv(["a"], [['x,"y"'], ["p\nq"]])).toBe('a\r\n"x,""y"""\r\n"p\nq"');
	});
	it("keeps Persian headers as they are", () => {
		expect(toCsv(["زمان", "پردازنده"], [])).toBe("زمان,پردازنده");
	});
	it("writes the time as an ISO-like local date Excel reads", () => {
		const ts = Date.UTC(2026, 10, 8, 10, 30, 5) / 1000;
		expect(csvTime(ts, 0)).toBe("2026-11-08 10:30:05");
		expect(csvTime(ts, -210)).toBe("2026-11-08 14:00:05");
	});
	it("starts the file with a UTF-8 byte order mark", async () => {
		const bytes = new Uint8Array(await csvBlob("زمان").arrayBuffer());
		expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
		expect(csvBlob("x").type).toContain("utf-8");
	});
});
