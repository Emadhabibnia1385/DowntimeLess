import { describe, expect, it } from "vitest";
import type { PingCell } from "@/api/generated/model";
import { buildMatrix, healthOf, numberOrNull } from "./matrix";

const limits = { loss_warn: 10, loss_crit: 50 };

const cell = (
	from_id: number,
	from_name: string,
	to_id: number | null,
	to_name: string,
	loss: number | null,
): PingCell => ({
	from_id,
	from_name,
	to_id,
	to_name,
	target: `10.0.0.${to_id ?? 99}`,
	loss_pct: loss,
	rtt_ms: 12,
	ts: 1,
});

describe("healthOf", () => {
	it("follows the alert thresholds", () => {
		expect(healthOf(0, limits)).toBe("ok");
		expect(healthOf(10, limits)).toBe("degraded");
		expect(healthOf(49.9, limits)).toBe("degraded");
		expect(healthOf(50, limits)).toBe("down");
		expect(healthOf(null, limits)).toBe("unknown");
	});
});

describe("numberOrNull", () => {
	it("keeps numbers only", () => {
		expect(numberOrNull(3)).toBe(3);
		expect(numberOrNull(null)).toBeNull();
		expect(numberOrNull("3")).toBeNull();
	});
});

describe("buildMatrix", () => {
	// Iran relays 1 and 2 ping foreign servers 10 and 11; relay 2 has not measured server 11
	const matrix = buildMatrix([
		cell(1, "iran-b", 10, "de-a", 0),
		cell(2, "iran-a", 10, "de-a", 20),
		cell(1, "iran-b", 11, "nl-a", 60),
	]);

	it("puts foreign servers down the side and Iran relays along the top", () => {
		expect(matrix.rows.map((row) => row.name)).toEqual(["de-a", "nl-a"]);
		expect(matrix.columns.map((column) => column.name)).toEqual(["iran-a", "iran-b"]);
	});

	it("finds the ping from a relay to a foreign server, if one was measured", () => {
		expect(matrix.cell(10, "id:2")?.loss_pct).toBe(20);
		expect(matrix.cell(11, "id:1")?.loss_pct).toBe(60);
		expect(matrix.cell(11, "id:2")).toBeUndefined();
	});

	it("skips a ping whose destination is not a known server", () => {
		expect(buildMatrix([cell(1, "iran-a", null, "1.1.1.1", 0)]).rows).toEqual([]);
	});

	it("is empty for no measurements", () => {
		expect(buildMatrix([]).rows).toEqual([]);
		expect(buildMatrix([]).columns).toEqual([]);
	});
});
