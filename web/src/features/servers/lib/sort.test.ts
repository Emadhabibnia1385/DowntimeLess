import { describe, expect, it } from "vitest";
import type { ServerOut } from "@/api/generated/model";
import { nextSort, sortServers } from "./sort";

const server = (id: number, name: string, cpu: number | null, rx: number | null): ServerOut =>
	({
		id,
		name,
		alias: "",
		role: "exit",
		status: "online",
		latest: { cpu_pct: cpu, rx_bps: rx, failed_units: [], reboot_required: false },
	}) as unknown as ServerOut;

const fleet = [server(1, "ب", 10, 5), server(2, "الف", 90, null), server(3, "ج", 50, 20)];

describe("sortServers", () => {
	it("keeps the given order with no sort", () => {
		expect(sortServers(fleet, null).map((s) => s.id)).toEqual([1, 2, 3]);
	});
	it("orders by a number, highest first", () => {
		const sorted = sortServers(fleet, { key: "cpu", direction: "desc" });
		expect(sorted.map((s) => s.id)).toEqual([2, 3, 1]);
	});
	it("puts servers without a value last in both directions", () => {
		expect(sortServers(fleet, { key: "download", direction: "asc" }).map((s) => s.id)).toEqual([
			1, 3, 2,
		]);
		expect(sortServers(fleet, { key: "download", direction: "desc" }).map((s) => s.id)).toEqual([
			3, 1, 2,
		]);
	});
	it("orders names in Persian", () => {
		expect(sortServers(fleet, { key: "name", direction: "asc" }).map((s) => s.id)[0]).toBe(2);
	});
});

describe("nextSort", () => {
	it("goes first direction, opposite, then off", () => {
		const a = nextSort(null, "cpu", "desc");
		expect(a).toEqual({ key: "cpu", direction: "desc" });
		const b = nextSort(a, "cpu", "desc");
		expect(b).toEqual({ key: "cpu", direction: "asc" });
		expect(nextSort(b, "cpu", "desc")).toBeNull();
	});
	it("starts over on another column", () => {
		expect(nextSort({ key: "cpu", direction: "asc" }, "ram", "desc")).toEqual({
			key: "ram",
			direction: "desc",
		});
	});
});
