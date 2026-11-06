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
	const matrix = buildMatrix([
		cell(2, "relay-b", 1, "exit-a", 0),
		cell(1, "exit-a", 2, "relay-b", 20),
		cell(2, "relay-b", null, "1.1.1.1", 0),
	]);

	it("lists each source once and each destination once", () => {
		expect(matrix.rows.map((row) => row.name)).toEqual(["exit-a", "relay-b"]);
		expect(matrix.columns.map((column) => column.name)).toEqual(["1.1.1.1", "exit-a", "relay-b"]);
	});

	it("finds the cell for a pair, if one was measured", () => {
		expect(matrix.cell(1, "id:2")?.loss_pct).toBe(20);
		expect(matrix.cell(2, "id:1")?.loss_pct).toBe(0);
		expect(matrix.cell(1, "id:1")).toBeUndefined();
	});

	it("is empty for no measurements", () => {
		expect(buildMatrix([]).rows).toEqual([]);
	});
});
