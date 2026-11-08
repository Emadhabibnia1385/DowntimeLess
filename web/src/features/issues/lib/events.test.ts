import { describe, expect, it } from "vitest";
import type { EventOut } from "@/api/generated/model";
import { describeEvent, EVENT_KINDS, kindLabel } from "./events";

const event = (kind: string, detail: Record<string, unknown> = {}, title = "raw"): EventOut => ({
	id: 1,
	ts: 1_800_000_000,
	server_id: 1,
	server: "de-1",
	kind,
	title,
	detail,
});

describe("describeEvent", () => {
	it("writes agent updates, IP changes and job results in Persian from the detail", () => {
		expect(describeEvent(event("agent_updated", { old: "0.2.7", new: "0.2.8" }))).toBe(
			"نسخهٔ agent از 0.2.7 به 0.2.8",
		);
		expect(describeEvent(event("ip_changed", { old: "1.1.1.1", new: "2.2.2.2" }))).toContain(
			"2.2.2.2",
		);
		expect(describeEvent(event("job_done", { job_kind: "ping", status: "ok" }))).toBe(
			"کار ping تمام شد: موفق",
		);
		expect(describeEvent(event("acct_toggled", { acct_on: false }))).toContain("خاموش");
	});

	it("names a removed server from the title and falls back to the title for unknown kinds", () => {
		expect(describeEvent(event("server_removed", {}, "old-1"))).toContain("old-1");
		expect(describeEvent(event("brand_new_kind", {}, "something happened"))).toBe(
			"something happened",
		);
	});

	it("shows the title when an old event has no detail", () => {
		expect(describeEvent(event("agent_updated", {}, "de-1: agent 1 -> 2"))).toBe(
			"de-1: agent 1 -> 2",
		);
	});

	it("says which issue was acknowledged and for how long", () => {
		expect(describeEvent(event("issue_acked", { code: "cpu", mode: "24h" }))).toBe(
			"مشکل cpu پذیرفته شد (۲۴ ساعت)",
		);
	});

	it("labels every kind the master can write", () => {
		expect(EVENT_KINDS).toHaveLength(15);
		for (const kind of EVENT_KINDS) expect(kindLabel(kind)).not.toBe(kind);
		expect(kindLabel("mystery")).toBe("mystery");
	});
});
