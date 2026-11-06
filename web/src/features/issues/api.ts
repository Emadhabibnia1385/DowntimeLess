import { useOverviewIssues } from "@/api/generated/overview/overview";

/** The current problems, refreshed every 15 seconds. */
export function useIssues() {
	return useOverviewIssues({ query: { refetchInterval: 15_000 } });
}
