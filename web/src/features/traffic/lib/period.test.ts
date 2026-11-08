import { describe, expect, it } from "vitest";
import {
	dayStart,
	dayText,
	defaultCustom,
	gregorianMonth,
	jalaliMonth,
	jalaliOf,
	parseDay,
	periodDays,
	periodWindow,
	tehranDay,
} from "./period";

const day = (text: string) => parseDay(text) as number;
// Wednesday 2026-11-04 14:00 in Tehran, which is 10:30 UTC
const NOW = Date.UTC(2026, 10, 4, 10, 30) / 1000;

describe("Tehran days", () => {
	it("counts the day from Tehran midnight, not UTC midnight", () => {
		expect(dayText(tehranDay(Date.UTC(2026, 9, 22, 20, 29, 59) / 1000))).toBe("2026-10-22");
		expect(dayText(tehranDay(Date.UTC(2026, 9, 22, 20, 30, 0) / 1000))).toBe("2026-10-23");
		expect(dayStart(day("2026-10-23"))).toBe(Date.UTC(2026, 9, 22, 20, 30) / 1000);
	});

	it("rejects dates that do not exist", () => {
		expect(parseDay("2026-02-30")).toBeNull();
		expect(parseDay("2026-13-01")).toBeNull();
		expect(parseDay("26-1-1")).toBeNull();
		expect(parseDay(undefined)).toBeNull();
	});
});

describe("Jalali months", () => {
	it("starts Aban on 23 October and Mehr on 23 September", () => {
		const [aban, azar] = jalaliMonth(day("2026-11-04"));
		expect(dayText(aban)).toBe("2026-10-23");
		expect(dayText(azar)).toBe("2026-11-22");
		expect(jalaliOf(aban)).toEqual({ year: 1405, month: 8, day: 1 });
		const [mehr, abanAgain] = jalaliMonth(day("2026-11-04"), 1);
		expect(dayText(mehr)).toBe("2026-09-23");
		expect(abanAgain).toBe(aban);
	});

	it("has 31 days in the first six months, 30 in the next five", () => {
		const lengths = [
			day("2026-04-01"),
			day("2026-05-01"),
			day("2026-06-01"),
			day("2026-07-01"),
		].map((d) => {
			const [from, to] = jalaliMonth(d);
			return to - from;
		});
		expect(lengths).toEqual([31, 31, 31, 31]);
		const mehr = jalaliMonth(day("2026-10-01"));
		expect(mehr[1] - mehr[0]).toBe(30);
		const azar = jalaliMonth(day("2026-12-01"));
		expect(jalaliOf(azar[0]).month).toBe(9);
		expect(azar[1] - azar[0]).toBe(30);
	});

	it("gives Esfand 29 days, and 30 in a leap year", () => {
		const common = jalaliMonth(day("2027-03-10")); // Esfand 1405
		expect(common[1] - common[0]).toBe(29);
		expect(dayText(common[1])).toBe("2027-03-21");
		const leap = jalaliMonth(day("2025-03-10")); // Esfand 1403
		expect(leap[1] - leap[0]).toBe(30);
		expect(dayText(leap[1])).toBe("2025-03-21");
	});

	it("goes back across the year end", () => {
		const [start, end] = jalaliMonth(day("2026-03-25"), 1); // Farvardin 1405 -> Esfand 1404
		expect(jalaliOf(start)).toEqual({ year: 1404, month: 12, day: 1 });
		expect(dayText(end)).toBe("2026-03-21");
	});
});

describe("Gregorian months", () => {
	it("covers the month and the previous one", () => {
		const [from, to] = gregorianMonth(day("2026-11-04"));
		expect([dayText(from), dayText(to)]).toEqual(["2026-11-01", "2026-12-01"]);
		const [pf, pt] = gregorianMonth(day("2026-11-04"), 1);
		expect([dayText(pf), dayText(pt)]).toEqual(["2026-10-01", "2026-11-01"]);
		expect(dayText(gregorianMonth(day("2026-01-15"), 1)[0])).toBe("2025-12-01");
	});
});

describe("periods", () => {
	const days = (id: Parameters<typeof periodDays>[0]["id"]) => {
		const range = periodDays({ id }, NOW);
		return range ? [dayText(range[0]), dayText(range[1])] : null;
	};

	it("resolves every preset to whole days ending after today", () => {
		expect(days("today")).toEqual(["2026-11-04", "2026-11-05"]);
		expect(days("yesterday")).toEqual(["2026-11-03", "2026-11-04"]);
		expect(days("7d")).toEqual(["2026-10-29", "2026-11-05"]);
		expect(days("30d")).toEqual(["2026-10-06", "2026-11-05"]);
		expect(days("month")).toEqual(["2026-11-01", "2026-12-01"]);
		expect(days("prev-month")).toEqual(["2026-10-01", "2026-11-01"]);
		expect(days("jmonth")).toEqual(["2026-10-23", "2026-11-22"]);
		expect(days("prev-jmonth")).toEqual(["2026-09-23", "2026-10-23"]);
	});

	it("turns days into Tehran midnights in epoch seconds", () => {
		const window = periodWindow({ id: "today" }, NOW);
		expect(window).toEqual({
			since: Date.UTC(2026, 10, 3, 20, 30) / 1000,
			until: Date.UTC(2026, 10, 4, 20, 30) / 1000,
		});
	});

	it("includes the last day of a custom range and refuses wrong ones", () => {
		expect(periodDays({ id: "custom", from: "2026-10-01", to: "2026-10-01" }, NOW)).toEqual([
			day("2026-10-01"),
			day("2026-10-01") + 1,
		]);
		expect(periodWindow({ id: "custom", from: "2026-10-05", to: "2026-10-01" }, NOW)).toBeNull();
		expect(periodWindow({ id: "custom", from: "2025-01-01", to: "2026-01-02" }, NOW)).toBeNull();
		expect(
			periodWindow({ id: "custom", from: "2025-11-04", to: "2026-11-04" }, NOW),
		).not.toBeNull();
		expect(periodWindow({ id: "custom" }, NOW)).toBeNull();
	});

	it("starts a custom range as the last 7 days", () => {
		expect(defaultCustom(NOW)).toEqual({ id: "custom", from: "2026-10-29", to: "2026-11-04" });
	});
});
