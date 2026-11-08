import { describe, expect, it } from "vitest";
import type { Latest } from "@/api/generated/model";
import { cpuUsage, diskUsage, ramUsage } from "./usage";

const latest = (over: Partial<Latest>): Latest =>
	({ failed_units: [], reboot_required: false, ...over }) as Latest;

describe("usage", () => {
	it("gives the busy cores out of the total, bare, when the agent reports them", () => {
		const u = cpuUsage(latest({ cpu_pct: 55, cpu_cores: 4 }));
		expect(u?.percent).toContain("۵۵");
		expect(u?.detail).toBe("۲٫۲ از ۴");
	});
	it("gives only the percent while the agent does not send cores", () => {
		expect(cpuUsage(latest({ cpu_pct: 10 }))?.detail).toBeNull();
		expect(cpuUsage(latest({}))).toBeNull();
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
