import { useOverviewPingMatrix } from "@/api/generated/overview/overview";

/** The latest Iran-to-abroad pings, refreshed every 30 seconds like the agents report. */
export function usePingMatrix() {
	return useOverviewPingMatrix({ query: { refetchInterval: 30_000 } });
}
