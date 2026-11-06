import {
	Button,
	ConfirmDialog,
	type DataColumn,
	DataTable,
	SectionCard,
	StatusChip,
} from "@nyxon/nasim";
import { useState } from "react";
import type { JobOut, ServerOut } from "@/api/generated/model";
import { BoltIcon, PingIcon, PowerIcon, RefreshIcon } from "@/shared/icons";
import { formatDateTime, t } from "@/strings";
import { useQueueJobs, useServerJobs } from "../api";
import { SPEEDTEST_DOWN_URL, SPEEDTEST_UP_URL, jobResultText } from "../lib/jobs";
import { PingDialog } from "./PingDialog";

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

const columns: DataColumn<JobOut>[] = [
	{ id: "kind", header: t.server.jobKind, isRowHeader: true, cell: (job) => kindLabel(job.kind) },
	{
		id: "status",
		header: t.server.jobStatus,
		cell: (job) => (
			<StatusChip tone={TONES[job.status] ?? "neutral"} label={statusLabel(job.status)} size="sm" />
		),
	},
	{ id: "result", header: t.server.jobResult, cell: (job) => jobResultText(job) },
	{ id: "created", header: t.server.jobCreated, cell: (job) => formatDateTime(job.created_at) },
];

type Mutating = "apt_upgrade_safe" | "reboot";

const CONFIRMS: Record<Mutating, { title: string; body: string }> = {
	apt_upgrade_safe: { title: t.server.confirmUpgradeTitle, body: t.server.confirmUpgrade },
	reboot: { title: t.server.confirmRebootTitle, body: t.server.confirmReboot },
};

// Recent jobs and the buttons that queue new ones; mutating jobs ask first and need permission.
export function JobsSection({ server, canManage }: { server: ServerOut; canManage: boolean }) {
	const jobs = useServerJobs(server.id);
	const queue = useQueueJobs(server.id);
	const [pinging, setPinging] = useState(false);
	const [confirming, setConfirming] = useState<Mutating | null>(null);
	const mayChange = server.permission !== "read";
	const confirm = confirming ? CONFIRMS[confirming] : null;
	return (
		<SectionCard
			title={t.server.jobs}
			actions={
				canManage ? (
					<div className="flex flex-wrap gap-2">
						<Button size="sm" variant="secondary" onPress={() => setPinging(true)}>
							<PingIcon aria-hidden />
							{t.server.jobPing}
						</Button>
						<Button
							size="sm"
							variant="secondary"
							isPending={queue.isPending}
							onPress={() =>
								queue.mutate([
									{ kind: "speedtest_down", args: { url: SPEEDTEST_DOWN_URL } },
									{ kind: "speedtest_up", args: { url: SPEEDTEST_UP_URL } },
								])
							}
						>
							<BoltIcon aria-hidden />
							{t.server.jobSpeedtest}
						</Button>
						{mayChange ? (
							<>
								<Button
									size="sm"
									variant="outline"
									onPress={() => setConfirming("apt_upgrade_safe")}
								>
									<RefreshIcon aria-hidden />
									{t.server.jobUpgrade}
								</Button>
								<Button size="sm" variant="danger-soft" onPress={() => setConfirming("reboot")}>
									<PowerIcon aria-hidden />
									{t.server.jobReboot}
								</Button>
							</>
						) : null}
					</div>
				) : undefined
			}
		>
			<DataTable
				ariaLabel={t.server.jobsLabel}
				columns={columns}
				rows={jobs.data}
				getRowId={(job) => String(job.id)}
				status={jobs.isPending ? "loading" : jobs.isError ? "error" : "ready"}
				onRetry={() => void jobs.refetch()}
				empty={t.server.jobsEmpty}
				cards="md"
			/>
			<PingDialog serverId={server.id} isOpen={pinging} onOpenChange={setPinging} />
			<ConfirmDialog
				isOpen={confirming !== null}
				onOpenChange={(open) => !open && setConfirming(null)}
				tone="danger"
				title={confirm?.title ?? ""}
				description={confirm?.body}
				confirmLabel={t.server.confirmRun}
				isPending={queue.isPending}
				onConfirm={() => {
					if (confirming) queue.mutate([{ kind: confirming, args: {} }]);
					setConfirming(null);
				}}
			/>
		</SectionCard>
	);
}
