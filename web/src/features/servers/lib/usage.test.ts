import { describe, expect, it } from "vitest";
import type { Latest } from "@/api/generated/model";
import { cpuUsage, diskUsage, ramUsage } from "./usage";

const latest = (over: Partial<Latest>): Latest =>
	({ failed_units: [], reboot_required: false, ...over }) as Latest;

describe("usage", () => {
	it("gives the CPU as a percent only, with or without cores reported", () => {
		for (const over of [{ cpu_pct: 75 }, { cpu_pct: 75, cpu_cores: 4 }]) {
			const u = cpuUsage(latest(over));
			expect(u?.percent).toContain("۷۵");
			expect(u?.detail).toBeNull();
		}
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
