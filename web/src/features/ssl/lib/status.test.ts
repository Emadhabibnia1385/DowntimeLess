import { describe, expect, it } from "vitest";
import { autoRenewStatus, certStatus, daysLeftLabel, summarize } from "./status";

const row = (level: string, days_left: number | null, error: string | null = null) => ({
	level,
	days_left,
	error,
	checked_at: 1_790_000_000,
});

describe("daysLeftLabel", () => {
	it("says expired, today or the days in Persian digits", () => {
		expect(daysLeftLabel(-2)).toBe("منقضی شده");
		expect(daysLeftLabel(0)).toBe("امروز منقضی می‌شود");
		expect(daysLeftLabel(3)).toBe("۳ روز مانده");
	});
});

describe("certStatus", () => {
	it("is healthy in words when the level is ok", () => {
		expect(certStatus(row("ok", 60))).toEqual({ tone: "success", label: "سالم" });
	});

	it("counts the days when a warning or critical level is not yet expired", () => {
		expect(certStatus(row("warning", 15))).toEqual({ tone: "warning", label: "۱۵ روز مانده" });
		expect(certStatus(row("critical", 3))).toEqual({ tone: "danger", label: "۳ روز مانده" });
	});

	it("calls an expired certificate expired", () => {
		expect(certStatus(row("critical", -1))).toEqual({ tone: "danger", label: "منقضی شده" });
	});

	it("reports a failed check before anything else", () => {
		expect(certStatus(row("critical", null, "اتصال ممکن نشد"))).toEqual({
			tone: "danger",
			label: "بررسی ناموفق",
		});
	});

	it("tells a domain not yet checked from an unknown date", () => {
		expect(certStatus({ ...row("ok", null), checked_at: null }).label).toBe("هنوز بررسی نشده");
		expect(certStatus(row("ok", null)).label).toBe("نامشخص");
	});
});

describe("autoRenewStatus", () => {
	it("words on, off and unknown", () => {
		expect(autoRenewStatus("on")).toEqual({ tone: "success", label: "فعال" });
		expect(autoRenewStatus("off")).toEqual({ tone: "warning", label: "غیرفعال" });
		expect(autoRenewStatus("unknown").label).toBe("نامشخص (فقط بررسی بیرونی)");
	});
});

describe("summarize", () => {
	it("counts each level and the certificates that do not renew", () => {
		const rows = [
			{ level: "ok", auto_renew: "on" },
			{ level: "warning", auto_renew: "off" },
			{ level: "critical", auto_renew: "unknown" },
			{ level: "critical", auto_renew: "off" },
		];
		expect(summarize(rows)).toEqual({ total: 4, expiring: 1, critical: 2, autoRenewOff: 2 });
	});
});
