import { describe, expect, it } from "vitest";
import { bucketSamples, isRange, peakOf } from "./chart";

const samples = (values: (number | null)[]) =>
	values.map((value, index) => ({ ts: 1000 + index * 30, value }));

describe("bucketSamples", () => {
	it("keeps every sample when there are few", () => {
		const bars = bucketSamples(samples([1, 2, 3]), "mean", 60);
		expect(bars.map((bar) => bar.value)).toEqual([1, 2, 3]);
	});

	it("averages levels when merging samples into bars", () => {
		const bars = bucketSamples(samples([10, 20, 30, 50]), "mean", 2);
		expect(bars).toEqual([
			{ ts: 1000, value: 15 },
			{ ts: 1060, value: 40 },
		]);
	});

	it("adds traffic when merging samples into bars", () => {
		const bars = bucketSamples(samples([100, 200, 300, 400, 500]), "sum", 2);
		expect(bars.map((bar) => bar.value)).toEqual([600, 900]);
	});

	it("skips gaps instead of counting them as zero", () => {
		expect(bucketSamples(samples([null, 40]), "mean", 1)[0]?.value).toBe(40);
		expect(bucketSamples(samples([null, null]), "mean", 1)[0]?.value).toBeNull();
	});

	it("is empty for no samples", () => {
		expect(bucketSamples([], "mean")).toEqual([]);
	});

	it("never makes more bars than asked", () => {
		const many = samples(Array.from({ length: 361 }, (_, index) => index));
		expect(bucketSamples(many, "mean", 60).length).toBeLessThanOrEqual(60);
	});
});

describe("peakOf", () => {
	it("is the biggest bar, or zero for none", () => {
		expect(
			peakOf([
				{ ts: 1, value: 3 },
				{ ts: 2, value: null },
				{ ts: 3, value: 9 },
			]),
		).toBe(9);
		expect(peakOf([])).toBe(0);
	});
});

describe("isRange", () => {
	it("accepts only the ranges the master serves", () => {
		expect(["1h", "24h", "7d", "30d"].every(isRange)).toBe(true);
		expect(isRange("1y")).toBe(false);
		expect(isRange(undefined)).toBe(false);
	});
});
