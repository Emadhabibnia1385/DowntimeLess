import { useChecksPanel } from "@/api/generated/checks/checks";

/** The PasarGuard panel view, refreshed every 30 seconds. */
export function usePanel() {
	return useChecksPanel({ query: { refetchInterval: 30_000 } });
}

/** Whether some server of the workspace reports a panel; only then is the page in the nav. */
export function useHasPanel(): boolean {
	const panel = useChecksPanel({ query: { refetchInterval: 60_000, staleTime: 30_000 } });
	return (panel.data?.panels?.length ?? 0) > 0;
}
