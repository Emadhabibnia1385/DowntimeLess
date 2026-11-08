import { describe, expect, it } from "vitest";
import type { PingCell } from "@/api/generated/model";
import { rankLinks } from "./links";

const limits = { loss_warn: 10, loss_crit: 50 };

const cell = (to: number, loss: number | null, rtt: number | null): PingCell => ({
	from_id: 1,
	from_name: "ir-1",
	to_id: to,
	to_name: `de-${to}`,
	target: "10.0.0.1",
	loss_pct: loss,
	rtt_ms: rtt,
	ts: 1,
});

describe("rankLinks", () => {
	it("puts the worst link first and unmeasured ones last", () => {
		const ranked = rankLinks(
			[cell(1, 0, 300), cell(2, null, null), cell(3, 60, 20), cell(4, 15, 40), cell(5, 0, 90)],
			limits,
		);
		expect(ranked.map((link) => link.cell.to_id)).toEqual([3, 4, 1, 5, 2]);
		expect(ranked[0].health).toBe("down");
	});
});
