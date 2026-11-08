import { Button, SectionCard } from "@nyxon/nasim";
import { type ReactNode, useState } from "react";
import type { ServerOut } from "@/api/generated/model";
import {
	BoltIcon,
	ChartIcon,
	PingIcon,
	PowerIcon,
	RefreshIcon,
	TableIcon,
	TrashIcon,
	WrenchIcon,
} from "@/shared/icons";
import { t } from "@/strings";
import { useQueueJobs } from "../api";
import { SPEEDTEST_DOWN_URL, SPEEDTEST_UP_URL } from "../lib/jobs";
import { CheckDialog } from "./CheckDialog";
import { JobConfirm, type Mutating } from "./JobConfirm";
import { RecentJobs } from "./RecentJobs";
import { ToolDialog, type ToolKind } from "./ToolDialog";

function Group({ title, children }: { title: string; children: ReactNode }) {
	return (
		<div className="flex flex-col gap-2">
			<h3 className="text-xs font-semibold text-muted">{title}</h3>
			<div className="flex flex-wrap gap-2">{children}</div>
		</div>
	);
}

const INFO_TOOLS: { kind: string; label: string; icon: ReactNode }[] = [
	{ kind: "processes", label: t.server.toolProcesses, icon: <ChartIcon aria-hidden /> },
	{ kind: "ports", label: t.server.toolPorts, icon: <PingIcon aria-hidden /> },
	{ kind: "disk_usage", label: t.server.toolDisk, icon: <TableIcon aria-hidden /> },
];

// Checks, maintenance and a separate danger zone in one block, then the last jobs.
export function OperationsCard({ server, canManage }: { server: ServerOut; canManage: boolean }) {
	const queue = useQueueJobs(server.id);
	const [check, setCheck] = useState<"ping" | "tcp_check" | null>(null);
	const [tool, setTool] = useState<ToolKind | null>(null);
	const [confirming, setConfirming] = useState<Mutating | null>(null);
	return (
		<SectionCard title={t.server.ops} description={canManage ? t.server.opsHint : undefined}>
			<div className="flex flex-col gap-5">
				{canManage ? (
					<>
						<Group title={t.server.groupChecks}>
							<Button size="sm" variant="secondary" onPress={() => setCheck("ping")}>
								<PingIcon aria-hidden />
								{t.server.jobPing}
							</Button>
							<Button size="sm" variant="secondary" onPress={() => setCheck("tcp_check")}>
								<PingIcon aria-hidden />
								{t.server.jobTcp}
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
							<Button size="sm" variant="secondary" onPress={() => setTool("traceroute")}>
								<PingIcon aria-hidden />
								{t.server.toolTraceroute}
							</Button>
							<Button size="sm" variant="secondary" onPress={() => setTool("dns_check")}>
								<PingIcon aria-hidden />
								{t.server.toolDns}
							</Button>
							<Button size="sm" variant="secondary" onPress={() => setTool("http_check")}>
								<PingIcon aria-hidden />
								{t.server.toolHttp}
							</Button>
						</Group>
						<Group title={t.server.groupInfo}>
							{INFO_TOOLS.map((item) => (
								<Button
									key={item.kind}
									size="sm"
									variant="secondary"
									isPending={queue.isPending}
									onPress={() => queue.mutate([{ kind: item.kind, args: {} }])}
								>
									{item.icon}
									{item.label}
								</Button>
							))}
							<Button size="sm" variant="secondary" onPress={() => setTool("journal")}>
								<TableIcon aria-hidden />
								{t.server.toolJournal}
							</Button>
						</Group>
						<Group title={t.server.groupMaintenance}>
							<Button size="sm" variant="outline" onPress={() => setConfirming("apt_upgrade_safe")}>
								<WrenchIcon aria-hidden />
								{t.server.jobUpgrade}
							</Button>
							<Button size="sm" variant="outline" onPress={() => setConfirming("self_update")}>
								<RefreshIcon aria-hidden />
								{t.server.jobSelfUpdate}
							</Button>
							<Button size="sm" variant="outline" onPress={() => setTool("service_restart")}>
								<RefreshIcon aria-hidden />
								{t.server.toolRestart}
							</Button>
							<Button size="sm" variant="outline" onPress={() => setConfirming("vacuum_logs")}>
								<TrashIcon aria-hidden />
								{t.server.toolVacuum}
							</Button>
						</Group>
						<div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger px-3 py-2.5">
							<div className="min-w-0">
								<h3 className="text-xs font-semibold text-danger-soft-foreground">
									{t.server.groupDanger}
								</h3>
								<p className="text-xs text-muted">{t.server.dangerHint}</p>
							</div>
							<Button size="sm" variant="danger-soft" onPress={() => setConfirming("reboot")}>
								<PowerIcon aria-hidden />
								{t.server.jobReboot}
							</Button>
						</div>
					</>
				) : null}
				<RecentJobs serverId={server.id} />
			</div>
			{check ? (
				<CheckDialog
					key={check}
					serverId={server.id}
					kind={check}
					isOpen
					onOpenChange={(open) => !open && setCheck(null)}
				/>
			) : null}
			{tool ? (
				<ToolDialog
					key={tool}
					serverId={server.id}
					kind={tool}
					isOpen
					onOpenChange={(open) => !open && setTool(null)}
				/>
			) : null}
			<JobConfirm serverId={server.id} kind={confirming} onClose={() => setConfirming(null)} />
		</SectionCard>
	);
}
