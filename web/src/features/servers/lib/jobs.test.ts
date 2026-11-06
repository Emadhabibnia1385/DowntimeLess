import { describe, expect, it } from "vitest";
import { jobResultText } from "./jobs";

const job = (
	kind: string,
	status: string,
	result: Record<string, unknown> | null,
	error = null,
) => ({
	kind,
	status,
	result,
	error,
});

describe("jobResultText", () => {
	it("shows ping loss and round-trip time", () => {
		expect(jobResultText(job("ping", "ok", { loss_pct: 0, rtt_ms: 41.2 }))).toBe(
			"۰٪ · ۴۱٫۲ میلی‌ثانیه",
		);
	});

	it("shows only the loss when no reply came back", () => {
		expect(jobResultText(job("ping", "ok", { loss_pct: 100, rtt_ms: null }))).toBe("۱۰۰٪");
	});

	it("shows speed in megabits", () => {
		expect(jobResultText(job("speedtest_down", "ok", { mbps: 93.4 }))).toBe("۹۳٫۴ مگابیت بر ثانیه");
	});

	it("says whether a port answered", () => {
		expect(jobResultText(job("tcp_check", "ok", { open: true }))).toBe("باز");
		expect(jobResultText(job("tcp_check", "ok", { open: false }))).toBe("بسته");
	});

	it("passes a failure's own message through", () => {
		expect(jobResultText(job("ping", "error", null, "ValueError: invalid target" as never))).toBe(
			"ValueError: invalid target",
		);
	});

	it("has nothing to say about a job that has not finished or has no figures", () => {
		expect(jobResultText(job("ping", "queued", null))).toBe("—");
		expect(jobResultText(job("reboot", "ok", {}))).toBe("—");
	});
});
