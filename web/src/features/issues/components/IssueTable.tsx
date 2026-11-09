import { DataTable, EmptyState, StatusChip } from "@nyxon/nasim";
import { Link } from "@tanstack/react-router";
import type { Issue } from "@/api/generated/model";
import { formatNumber, t } from "@/strings";
import { AckButton } from "../acks";
import { FixJobButton } from "../fixes";
import { FixCommand, GuideButton } from "../guides";
import { type GroupItem, groupIssues, type IssueGroup } from "../lib/group";

const TONES = { critical: "danger", warning: "warning", info: "info" } as const;
const LABELS: Record<string, string> = t.severity;

function ServerLine({ item, title }: { item: GroupItem; title: string }) {
	const name =
		item.to === "server" && item.serverId !== null ? (
			<Link
				to="/servers/$serverId"
				params={{ serverId: String(item.serverId) }}
				className="font-medium text-accent-soft-foreground underline-offset-4 hover:underline"
			>
				{item.serverName}
			</Link>
		) : item.to === "panel" ? (
			<Link
				to="/panel"
				className="font-medium text-accent-soft-foreground underline-offset-4 hover:underline"
			>
				{item.serverName}
			</Link>
		) : item.to === "ssl" ? (
			<Link
				to="/ssl"
				className="font-medium text-accent-soft-foreground underline-offset-4 hover:underline"
			>
				{item.serverName || t.issues.openSsl}
			</Link>
		) : (
			<span className="font-medium">{item.serverName}</span>
		);
	return (
		<li className="flex items-center justify-between gap-4 py-0.5">
			<span className="flex flex-wrap items-center gap-2">
				{name}
				{item.recent > 1 ? (
					<StatusChip
						tone="warning"
						label={t.issueHistory.recurrence(formatNumber(item.recent))}
						size="sm"
					/>
				) : null}
			</span>
			<span className="flex items-center gap-2">
				<span className="tabular-nums text-muted">{item.value || t.common.none}</span>
				{item.fix && item.serverId !== null ? (
					<FixJobButton
						serverId={item.serverId}
						server={item.serverName}
						title={title}
						fix={item.fix}
					/>
				) : null}
				<AckButton target={{ key: item.id, title, server: item.serverName }} />
			</span>
		</li>
	);
}

// One row per kind of problem: its servers and levels first, then the suggested step.
export function IssueTable({ issues }: { issues: readonly Issue[] }) {
	const groups = groupIssues(issues);
	if (groups.length === 0)
		return <EmptyState title={t.issues.emptyTitle} description={t.issues.empty} />;
	return (
		<DataTable<IssueGroup>
			ariaLabel={t.issues.listLabel}
			getRowId={(group) => group.family}
			rows={groups}
			status="ready"
			columns={[
				{
					id: "problem",
					header: t.issues.columns.problem,
					isRowHeader: true,
					cell: (group) => (
						<div className="flex flex-col items-start gap-1">
							<StatusChip tone={TONES[group.severity]} label={LABELS[group.severity]} size="sm" />
							<span className="font-semibold">{group.title}</span>
							<GuideButton target={{ code: group.family, title: group.title }} />
						</div>
					),
				},
				{
					id: "servers",
					header: t.issues.columns.servers,
					cell: (group) => (
						<ul className="flex min-w-60 flex-col text-sm">
							{group.items.map((item) => (
								<ServerLine key={item.id} item={item} title={group.title} />
							))}
						</ul>
					),
				},
				{
					id: "next",
					header: t.issues.columns.next,
					cell: (group) => (
						<div className="flex flex-col gap-2">
							<span className="block max-w-80 whitespace-normal text-sm text-muted">
								{group.suggestion}
							</span>
							<FixCommand code={group.family} />
						</div>
					),
				},
			]}
		/>
	);
}
