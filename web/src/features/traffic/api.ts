import { useTrafficSeries, useTrafficSummary } from "@/api/generated/traffic/traffic";
import { TEHRAN_OFFSET_MIN, type Window } from "./lib/period";

const REFRESH_MS = 60_000;

/** Per-server and fleet totals for a window; waits while the window is not valid. */
export function useSummary(window: Window | null) {
	return useTrafficSummary(
		{ since: window?.since, until: window?.until, tz_offset_min: TEHRAN_OFFSET_MIN },
		{ query: { enabled: window !== null, refetchInterval: REFRESH_MS } },
	);
}

/** The curve of one server, or of the fleet, over a window. */
export function useSeries(window: Window | null, serverId: number | null) {
	return useTrafficSeries(
		{
			since: window?.since,
			until: window?.until,
			server_id: serverId ?? undefined,
			tz_offset_min: TEHRAN_OFFSET_MIN,
		},
		{ query: { enabled: window !== null, refetchInterval: REFRESH_MS } },
	);
}
