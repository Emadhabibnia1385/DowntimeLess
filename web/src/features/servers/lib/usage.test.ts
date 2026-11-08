import { describe, expect, it } from "vitest";
import type { Latest } from "@/api/generated/model";
import { t } from "@/strings";
import { cpuUsage, diskUsage, ramUsage } from "./usage";

const latest = (over: Partial<Latest>): Latest =>
	({ failed_units: [], reboot_required: false, ...over }) as Latest;

describe("usage", () => {
	it("says how many cores are busy", () => {
		const u = cpuUsage(latest({ cpu_pct: 75, cpu_cores: 4 }));
		expect(u?.percent).toContain("۷۵");
		expect(u?.detail).toContain("۳");
		expect(u?.detail).toContain("۴");
	});
	it("gives only the percent while the agent does not send cores", () => {
		expect(cpuUsage(latest({ cpu_pct: 10 }))?.detail).toBe(t.servers.coresUnknown);
	});
	it("shows used and total gigabytes for memory and disk", () => {
		const ram = ramUsage(latest({ ram_pct: 50, ram_used_mb: 4096, ram_total_mb: 8192 }));
		expect(ram?.detail).toContain("۴");
		expect(ram?.detail).toContain("۸");
		expect(
			diskUsage(latest({ disk_pct: 20, disk_used_gb: 20, disk_total_gb: 100 }))?.detail,
		).toContain("۱۰۰");
	});
	it("is null with no reading", () => {
		expect(cpuUsage(latest({}))).toBeNull();
	});
});
