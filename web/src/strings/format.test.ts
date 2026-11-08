import { describe, expect, it } from "vitest";
import {
	formatBitRate,
	formatBytes,
	formatClock,
	formatDate,
	formatDateTime,
	formatDecimal,
	formatDuration,
	formatMs,
	formatNumber,
	formatPercent,
	formatRelativeTime,
	formatTick,
} from "./format";

// 2026-10-14 12:30:00 UTC, which is 22 Mehr 1405 in the Jalali calendar.
const MOMENT = Date.UTC(2026, 9, 14, 12, 30) / 1000;

describe("numbers", () => {
	it("writes Persian digits with a Persian group separator", () => {
		expect(formatNumber(1234567)).toBe("۱٬۲۳۴٬۵۶۷");
		expect(formatNumber(0)).toBe("۰");
	});

	it("rounds to the requested decimals with a Persian decimal mark", () => {
		expect(formatDecimal(12.345, 1)).toBe("۱۲٫۳");
		expect(formatDecimal(5, 2)).toBe("۵");
	});

	it("formats a value that is already a percentage", () => {
		expect(formatPercent(12.5)).toBe("۱۲٫۵٪");
		expect(formatPercent(0)).toBe("۰٪");
		expect(formatPercent(100)).toBe("۱۰۰٪");
	});
});

describe("sizes and rates", () => {
	it("picks the byte unit that reads best", () => {
		expect(formatBytes(0)).toBe("۰ بایت");
		expect(formatBytes(1023)).toBe("۱٬۰۲۳ بایت");
		expect(formatBytes(1024)).toBe("۱ کیلوبایت");
		expect(formatBytes(1.5 * 1024 ** 3)).toBe("۱٫۵ گیگابایت");
		expect(formatBytes(250 * 1024 ** 2)).toBe("۲۵۰ مگابایت");
	});

	it("never goes past terabytes and ignores negatives", () => {
		expect(formatBytes(5000 * 1024 ** 4)).toBe("۵٬۰۰۰ ترابایت");
		expect(formatBytes(-5)).toBe("۰ بایت");
	});

	it("counts network rates in thousands", () => {
		expect(formatBitRate(999)).toBe("۹۹۹ بیت بر ثانیه");
		expect(formatBitRate(1_500_000)).toBe("۱٫۵ مگابیت بر ثانیه");
		expect(formatBitRate(2_000_000_000)).toBe("۲ گیگابیت بر ثانیه");
	});

	it("writes a round-trip time", () => {
		expect(formatMs(41.24)).toBe("۴۱٫۲ میلی‌ثانیه");
	});
});

describe("durations", () => {
	it("uses the two largest non-zero units", () => {
		expect(formatDuration(3 * 86_400 + 4 * 3600 + 120)).toBe("۳ روز و ۴ ساعت");
		expect(formatDuration(3600 + 5 * 60)).toBe("۱ ساعت و ۵ دقیقه");
		expect(formatDuration(12 * 60)).toBe("۱۲ دقیقه");
	});

	it("falls back to seconds below a minute", () => {
		expect(formatDuration(42)).toBe("۴۲ ثانیه");
		expect(formatDuration(0)).toBe("۰ ثانیه");
	});
});

describe("dates", () => {
	it("writes a Jalali date with Persian digits", () => {
		expect(formatDate(MOMENT, "UTC")).toBe("۲۲ مهر ۱۴۰۵");
	});

	it("adds the time of day", () => {
		expect(formatDateTime(MOMENT, "UTC")).toContain("۲۲ مهر ۱۴۰۵");
		expect(formatDateTime(MOMENT, "UTC")).toContain("۱۲:۳۰");
	});

	it("labels a chart tick with the clock for a day or less and the date beyond", () => {
		expect(formatTick(MOMENT, 3600, "UTC")).toBe("۱۲:۳۰");
		expect(formatTick(MOMENT, 604_800, "UTC")).toContain("مهر");
	});

	it("says how long ago in Persian", () => {
		const now = MOMENT * 1000;
		expect(formatRelativeTime(MOMENT - 7200, now)).toBe("۲ ساعت پیش");
		expect(formatRelativeTime(MOMENT - 30, now)).toBe("۳۰ ثانیه پیش");
	});
});

describe("formatClock", () => {
	it("gives weekday, time with seconds and both calendars for the given zone", () => {
		const parts = formatClock(new Date("2026-11-08T14:35:45Z"), "Asia/Tehran");
		expect(parts).toEqual({
			weekday: "یکشنبه",
			time: "۱۸:۰۵:۴۵",
			gregorian: "۲۰۲۶/۱۱/۰۸",
			jalali: "۱۴۰۵/۰۸/۱۷",
		});
	});

	it("follows the zone, so the same moment reads differently elsewhere", () => {
		expect(formatClock(new Date("2026-11-08T14:35:45Z"), "UTC").time).toBe("۱۴:۳۵:۴۵");
	});
});
