import { useOverviewIssues } from "@/api/generated/overview/overview";
import { useIssuesHistory } from "@/api/generated/issues/issues";
import type { HistoryRange } from "./lib/tabs";

/** The current problems, refreshed every 15 seconds. */
export function useIssues() {
	return useOverviewIssues({ query: { refetchInterval: 15_000 } });
}

/** Everything that was active in the range, refreshed every 30 seconds. */
export function useHistory(range: HistoryRange) {
	return useIssuesHistory({ range }, { query: { refetchInterval: 30_000 } });
}
