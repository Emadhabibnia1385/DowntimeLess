import type { PingCell } from "@/api/generated/model";
import { type Health, healthOf, numberOrNull, type Thresholds } from "./matrix";

export type RankedLink = {
	cell: PingCell;
	loss: number | null;
	rtt: number | null;
	health: Health;
};

const RANK: Record<Health, number> = { down: 0, degraded: 1, ok: 2, unknown: 3 };

/** Every measured link, the worst first: by health, then packet loss, then round-trip time. */
export function rankLinks(cells: readonly PingCell[], limits: Thresholds): RankedLink[] {
	return cells
		.map((cell) => {
			const loss = numberOrNull(cell.loss_pct);
			return { cell, loss, rtt: numberOrNull(cell.rtt_ms), health: healthOf(loss, limits) };
		})
		.sort(
			(a, b) =>
				RANK[a.health] - RANK[b.health] ||
				(b.loss ?? 0) - (a.loss ?? 0) ||
				(b.rtt ?? 0) - (a.rtt ?? 0),
		);
}
