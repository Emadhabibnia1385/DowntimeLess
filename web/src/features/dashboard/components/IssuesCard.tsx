import { EmptyState, StaticTable, StatusChip } from "@nyxon/nasim";
import type { Issue } from "@/api/generated/model";
import {
	AckButton,
	ServerLabel,
	severityTone,
	splitAcked,
	useHistory,
	useIssues,
} from "@/features/issues";
import { useCanCheck } from "@/features/auth/session";
import { useServers } from "@/features/servers";
import { flagOf, formatDateTime, formatDuration, formatNumber, t } from "@/strings";
import { openSince, secondsSince, sortIssues } from "../lib/stats";
import { COMPACT_TABLE, DataCard } from "./DataCard";

const COPY = t.dashboard.issues;
const SHOWN = 8;
const SEVERITIES: Record<string, string> = t.severity;

function OpenFor({ since }: { since: number | undefined }) {
	if (since === undefined) return t.common.none;
	return (
		<span title={formatDateTime(since)} className="whitespace-nowrap tabular-nums">
			{formatDuration(secondsSince(since))}
		</span>
	);
}

// Current problems, worst first, with how long each has been open (from the incident log).
export function IssuesCard() {
	const issues = useIssues();
	const history = useHistory("24h");
	const servers = useServers();
	const canAck = useCanCheck();
	const flags = new Map((servers.data ?? []).map((server) => [server.id, flagOf(server.country)]));
	const since = openSince(history.data?.incidents ?? []);
	const row = (issue: Issue) => ({
		id: issue.id,
		cells: [
			<StatusChip
				key="severity"
				tone={severityTone(issue.severity)}
				label={SEVERITIES[issue.severity] ?? issue.severity}
				size="sm"
			/>,
			<ServerLabel
				key="server"
				serverId={issue.server_id}
				name={issue.server_name}
				flag={issue.server_id === null ? "" : (flags.get(issue.server_id) ?? "")}
			/>,
			<span key="title" title={issue.title} className="line-clamp-2 whitespace-normal text-sm">
				{issue.title}
			</span>,
			<OpenFor key="open" since={since.get(issue.id)} />,
			...(canAck
				? [
						<AckButton
							key="ack"
							target={{ key: issue.id, title: issue.title, server: issue.server_name ?? "" }}
						/>,
					]
				: []),
		],
	});
	return (
		<DataCard
			title={COPY.title}
			description={COPY.subtitle}
			href="/issues"
			linkLabel={COPY.all}
			query={issues}
		>
			{(all) => {
				const { open: items, acked } = splitAcked(all);
				const known = acked.length ? (
					<p className="text-xs text-muted">
						{t.issueAcks.onDashboard(formatNumber(acked.length))}
					</p>
				) : null;
				if (items.length === 0) {
					return (
						<div className="flex flex-col gap-3">
							<EmptyState title={COPY.emptyTitle} description={COPY.empty} />
							{known}
						</div>
					);
				}
				const shown = sortIssues(items, since).slice(0, SHOWN);
				const columns = [COPY.severity, COPY.server, COPY.problem, COPY.openFor];
				return (
					<div className="flex flex-col gap-3">
						<StaticTable
							caption={COPY.tableLabel}
							className={COMPACT_TABLE}
							columns={canAck ? [...columns, t.issueAcks.actionColumn] : columns}
							rows={shown.map(row)}
						/>
						{items.length > SHOWN ? (
							<p className="text-xs text-muted">{COPY.more(formatNumber(items.length - SHOWN))}</p>
						) : null}
						{known}
					</div>
				);
			}}
		</DataCard>
	);
}
