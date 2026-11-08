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
