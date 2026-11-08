import { describe, expect, it } from "vitest";
import { buildTrafficChart, busiestHour, pickUnit } from "./chart";

const GB = 1024 ** 3;

describe("traffic chart", () => {
	it("picks the unit of the biggest value", () => {
		expect(pickUnit(0).name).toBe("بایت");
		expect(pickUnit(5 * 1024 ** 2).name).toBe("مگابایت");
		expect(pickUnit(10 * GB).name).toBe("گیگابایت");
		expect(pickUnit(1.5 * 1024 ** 4).name).toBe("ترابایت");
		expect(pickUnit(5000 * 1024 ** 4).divisor).toBe(1024 ** 4);
	});

	it("scales both lines to one unit and prints the exact size in the tooltip", () => {
		const chart = buildTrafficChart([
			{ ts: 1, rx: 100 * GB, tx: 20 * GB },
			{ ts: 2, rx: 50 * GB, tx: 0 },
		]);
		expect(chart.times).toEqual([1, 2]);
		expect(chart.series[0]?.values).toEqual([100, 50]);
		expect(chart.series[1]?.values).toEqual([20, 0]);
		expect(chart.unit).toContain("گیگابایت");
		expect(chart.format(100)).toBe("۱۰۰ گیگابایت");
		expect(chart.axisFormat(2.5)).toBe("۲٫۵");
	});

	it("finds the busiest hour, or none", () => {
		const hours = Array.from({ length: 24 }, (_, hour) => ({ hour, rx: 0, tx: 0 }));
		expect(busiestHour(hours)).toBeNull();
		hours[9] = { hour: 9, rx: 5, tx: 5 };
		hours[21] = { hour: 21, rx: 20, tx: 1 };
		expect(busiestHour(hours)?.hour).toBe(21);
	});
});
