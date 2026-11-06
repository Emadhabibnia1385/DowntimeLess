import { useQueryClient } from "@tanstack/react-query";

/** Everything shown depends on a server or a threshold, so a change refreshes all of it. */
export function useRefreshAll() {
	const queryClient = useQueryClient();
	return () => queryClient.invalidateQueries();
}
