import { useTrafficSummary } from "@/api/generated/traffic/traffic";
import { TEHRAN_OFFSET_MIN } from "@/features/traffic";
import { useOverviewGet, useOverviewHistory } from "@/api/generated/overview/overview";

// The agents report every 30 seconds, so asking more often only repeats the same numbers.
const REFRESH_MS = 30_000;

/** The fleet's counts, refreshed every 30 seconds. */
export function useOverview() {
	return useOverviewGet({ query: { refetchInterval: REFRESH_MS } });
}

/** The whole fleet over a range, refreshed every 30 seconds. */
export function useFleetHistory(range: string) {
	return useOverviewHistory({ range }, { query: { refetchInterval: REFRESH_MS } });
}

/** Today's and yesterday's fleet traffic in Tehran days, refreshed every minute. */
export function useTodayTraffic() {
	return useTrafficSummary(
		{ tz_offset_min: TEHRAN_OFFSET_MIN },
		{ query: { refetchInterval: 60_000 } },
	);
}
