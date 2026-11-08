import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
	reportsBriefing,
	reportsChanges,
	useReportsHealth,
	useReportsPlaybook,
	useReportsPlaybooks,
} from "@/api/generated/reports/reports";
import { type Detail, PERIODS, type Period } from "./lib/tabs";

const REFRESH_MS = 60_000;

/** The briefing as Markdown text, refreshed every minute. */
export function useBriefing(detail: Detail) {
	return useQuery({
		queryKey: ["reports", "briefing-md", detail],
		queryFn: async ({ signal }) =>
			// the answer of format=md is text; the generated type describes the JSON form
			(await reportsBriefing({ format: "md", detail }, { signal })) as unknown as string,
		placeholderData: keepPreviousData,
		refetchInterval: REFRESH_MS,
	});
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

export function usePlaybooks() {
	return useReportsPlaybooks({}, { query: { staleTime: Number.POSITIVE_INFINITY } });
}

export function usePlaybook(code: string | null) {
	return useReportsPlaybook(code ?? "", {}, { query: { enabled: code !== null } });
}
