import { StatusChip } from "@nyxon/nasim";
import { formatRelativeTime, t } from "@/strings";
import { useServerJobs } from "../api";
import { jobResultText } from "../lib/jobs";

const MAX_JOBS = 8;

const kindLabel = (kind: string) =>
	(t.server.jobKinds as Record<string, string | undefined>)[kind] ?? kind;
const statusLabel = (status: string) =>
	(t.server.jobStatuses as Record<string, string | undefined>)[status] ?? status;

const TONES: Record<string, "success" | "danger" | "neutral" | "info"> = {
	ok: "success",
	error: "danger",
	rejected: "danger",
	queued: "neutral",
	sent: "info",
};

// The last few jobs on this server: what, how it went in a word, when, and the short result.
export function RecentJobs({ serverId }: { serverId: number }) {
	const jobs = useServerJobs(serverId);
	const recent = [...(jobs.data ?? [])]
		.sort((a, b) => b.created_at - a.created_at)
		.slice(0, MAX_JOBS);
	return (
		<div className="flex flex-col gap-2">
			<h3 className="text-sm font-semibold">{t.server.recentJobs}</h3>
			{recent.length === 0 ? (
				<p className="text-sm text-muted">{jobs.isPending ? "" : t.server.jobsEmpty}</p>
			) : (
				<ul className="flex flex-col divide-y divide-separator">
					{recent.map((job) => {
						const result = jobResultText(job);
						return (
							<li key={job.id} className="flex items-center justify-between gap-3 py-2">
								<div className="min-w-0">
									<p className="text-sm font-medium">{kindLabel(job.kind)}</p>
									<p className="truncate text-xs text-muted">
										{formatRelativeTime(job.created_at)}
										{result === t.common.none ? "" : ` · ${result}`}
									</p>
								</div>
								<StatusChip
									tone={TONES[job.status] ?? "neutral"}
									label={statusLabel(job.status)}
									size="sm"
								/>
							</li>
						);
					})}
				</ul>
			)}
		</div>
	);
}
