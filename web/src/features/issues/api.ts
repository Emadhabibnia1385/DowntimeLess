import { useQuery } from "@tanstack/react-query";
import { useOverviewIssues } from "@/api/generated/overview/overview";
import { useIssuesHistory } from "@/api/generated/issues/issues";
import { reportsChanges, useReportsHealth } from "@/api/generated/reports/reports";
import { type HistoryRange, PERIODS, type Period } from "./lib/tabs";

const REFRESH_MS = 60_000;

/** The current problems, refreshed every 15 seconds. */
export function useIssues() {
	return useOverviewIssues({ query: { refetchInterval: 15_000 } });
}

/** Everything that was active in the range, refreshed every 30 seconds. */
export function useHistory(range: HistoryRange) {
	return useIssuesHistory({ range }, { query: { refetchInterval: 30_000 } });
}

export function useHealth() {
	return useReportsHealth({}, { query: { refetchInterval: REFRESH_MS } });
}

/** Events of the last day, week or month, newest first. */
export function useChanges(period: Period) {
	return useQuery({
		queryKey: ["reports", "changes", period],
		queryFn: ({ signal }) =>
			reportsChanges({ since: Math.floor(Date.now() / 1000) - PERIODS[period] }, { signal }),
		refetchInterval: REFRESH_MS,
	});
}
