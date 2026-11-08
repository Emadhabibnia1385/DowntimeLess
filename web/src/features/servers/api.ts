import { toast } from "@nyxon/nasim";
import { useMutation } from "@tanstack/react-query";
import {
	serversCreateJob,
	useServersGet,
	useServersJobs,
	useServersList,
} from "@/api/generated/servers/servers";
import type { JobCreate } from "@/api/generated/model";
import { errorMessage } from "@/api/transport";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";

// The agent reports every 30 seconds, so asking more often only repeats the same numbers.
const REFRESH_MS = 30_000;
const WAITING_MS = 5_000;

/** The fleet, refreshed every 30 seconds. */
export function useServers() {
	return useServersList({ query: { refetchInterval: REFRESH_MS } });
}

export function useServer(serverId: number) {
	return useServersGet(serverId, { query: { refetchInterval: REFRESH_MS } });
}

export function useServerJobs(serverId: number) {
	// While a job waits for its result, look more often so the output shows soon after the report.
	return useServersJobs(serverId, {
		query: {
			refetchInterval: (query) =>
				(query.state.data ?? []).some((job) => job.status === "queued" || job.status === "sent")
					? WAITING_MS
					: REFRESH_MS,
		},
	});
}

/** Queues one or more jobs on a server, then says so and refreshes the job list. */
export function useQueueJobs(serverId: number, onQueued?: () => void) {
	const refresh = useRefreshAll();
	return useMutation({
		mutationFn: (jobs: JobCreate[]) =>
			Promise.all(jobs.map((job) => serversCreateJob(serverId, job))),
		onSuccess: () => {
			toast.success(t.server.jobQueued);
			void refresh();
			onQueued?.();
		},
		onError: (error) => toast.danger(errorMessage(error)),
	});
}
