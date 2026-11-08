import { Button, CopyButton, Modal, StaticTable, StatusChip } from "@nyxon/nasim";
import { useState } from "react";
import type { JobOut } from "@/api/generated/model";
import { formatRelativeTime, t } from "@/strings";
import { useServerJobs } from "../api";
import { jobOutput, jobResultText } from "../lib/jobs";

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

// The last few jobs on this server as a table: what, how it went, when, and the short result.
export function RecentJobs({ serverId }: { serverId: number }) {
	const jobs = useServerJobs(serverId);
	const [viewing, setViewing] = useState<JobOut | null>(null);
	const recent = [...(jobs.data ?? [])]
		.sort((a, b) => b.created_at - a.created_at)
		.slice(0, MAX_JOBS);
	return (
		<div className="flex flex-col gap-2">
			<h3 className="text-sm font-semibold">{t.server.recentJobs}</h3>
			{recent.length === 0 ? (
				<p className="text-sm text-muted">{jobs.isPending ? "" : t.server.jobsEmpty}</p>
			) : (
				<StaticTable
					caption={t.server.jobsTable}
					className="min-w-[28rem]"
					columns={[
						t.server.jobColKind,
						t.server.jobColStatus,
						t.server.jobColWhen,
						t.server.jobColResult,
					]}
					rows={recent.map((job) => ({
						id: String(job.id),
						cells: [
							kindLabel(job.kind),
							<StatusChip
								key="status"
								tone={TONES[job.status] ?? "neutral"}
								label={statusLabel(job.status)}
								size="sm"
							/>,
							<span key="when" className="whitespace-nowrap text-sm text-muted">
								{formatRelativeTime(job.created_at)}
							</span>,
							<div key="result" className="flex flex-wrap items-center gap-2 text-sm">
								{jobOutput(job) && jobResultText(job) === t.common.none ? null : (
									<span>{jobResultText(job)}</span>
								)}
								{jobOutput(job) ? (
									<Button size="sm" variant="secondary" onPress={() => setViewing(job)}>
										{t.server.outputShow}
									</Button>
								) : null}
							</div>,
						],
					}))}
				/>
			)}
			<Modal
				isOpen={viewing !== null}
				onOpenChange={(open) => !open && setViewing(null)}
				title={
					viewing ? `${t.server.outputTitle}: ${kindLabel(viewing.kind)}` : t.server.outputTitle
				}
				size="lg"
			>
				{viewing ? (
					<div className="flex flex-col gap-3">
						<pre
							dir="ltr"
							className="max-h-[60vh] overflow-auto whitespace-pre rounded-xl bg-surface-secondary p-3 text-start font-mono text-xs leading-5"
						>
							{jobOutput(viewing)}
						</pre>
						<CopyButton
							value={jobOutput(viewing) ?? ""}
							label={t.server.outputCopy}
							doneLabel={t.server.outputCopied}
							variant="secondary"
						/>
					</div>
				) : null}
			</Modal>
		</div>
	);
}
