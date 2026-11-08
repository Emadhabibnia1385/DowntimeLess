import { describe, expect, it } from "vitest";
import { evidenceRows } from "./evidence";

describe("evidenceRows", () => {
	it("labels and formats known measurements", () => {
		expect(evidenceRows({ disk_pct: 91.5, rtt_ms: 40, last_seen_s_ago: 4000 })).toEqual([
			{ key: "disk_pct", label: "دیسک", value: "۹۱٫۵٪", ltr: false },
			{ key: "rtt_ms", label: "تأخیر", value: "۴۰ میلی‌ثانیه", ltr: false },
			{ key: "last_seen_s_ago", label: "آخرین گزارش", value: "۱ ساعت و ۶ دقیقه", ltr: false },
		]);
	});

	it("keeps names and lists left to right", () => {
		const rows = evidenceRows({ to: "de-1", units: ["x-ui.service", "nginx.service"] });
		expect(rows.map((row) => [row.value, row.ltr])).toEqual([
			["de-1", true],
			["x-ui.service, nginx.service", true],
		]);
	});

	it("labels certificate evidence and keeps an error message in the page direction", () => {
		const rows = evidenceRows({ days_left: 3, error: "اتصال ممکن نشد" });
		expect(rows).toEqual([
			{ key: "days_left", label: "روز تا انقضا", value: "۳", ltr: false },
			{ key: "error", label: "خطا", value: "اتصال ممکن نشد", ltr: false },
		]);
	});

	it("shows an unknown key by its own name", () => {
		expect(evidenceRows({ mystery: 3 })[0]).toMatchObject({ label: "mystery", value: "۳" });
	});
});

describe("evidenceRows for the multi-relay ping issue", () => {
	it("labels the relays and the number of probes in Persian and joins the names", () => {
		const rows = evidenceRows({ relays: ["iran-1", "iran-2"], measured_by: 3, loss_pct: 40 });
		expect(rows.map((row) => row.label)).toEqual([
			"رله‌های دارای افت",
			"تعداد رله‌های سنجنده",
			"افت بسته",
		]);
		expect(rows[0].value).toBe("iran-1, iran-2");
	});
});
