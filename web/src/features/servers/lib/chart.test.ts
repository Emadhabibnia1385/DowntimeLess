import { describe, expect, it } from "vitest";
import { CHIP_RANGES, isRange, RANGES } from "./chart";

describe("isRange", () => {
	it("accepts only the ranges the master serves", () => {
		expect(["1h", "6h", "24h", "7d", "30d"].every(isRange)).toBe(true);
		expect(isRange("1y")).toBe(false);
		expect(isRange(undefined)).toBe(false);
	});
});

describe("CHIP_RANGES", () => {
	it("offers 6 hours, 24 hours, 7 days and 30 days, all served", () => {
		expect(CHIP_RANGES).toEqual(["6h", "24h", "7d", "30d"]);
		expect(CHIP_RANGES.every((range) => range in RANGES)).toBe(true);
	});
});
