import { EmptyState, StaticTable, StatusChip } from "@nyxon/nasim";
import type { Issue } from "@/api/generated/model";
import { ServerLabel, severityTone, useHistory, useIssues } from "@/features/issues";
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
			<span key="title" className="block whitespace-normal text-sm">
				{issue.title}
			</span>,
			<OpenFor key="open" since={since.get(issue.id)} />,
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
			{(items) => {
				if (items.length === 0) {
					return <EmptyState title={COPY.emptyTitle} description={COPY.empty} />;
				}
				const shown = sortIssues(items, since).slice(0, SHOWN);
				return (
					<div className="flex flex-col gap-3">
						<StaticTable
							caption={COPY.tableLabel}
							className={COMPACT_TABLE}
							columns={[COPY.severity, COPY.server, COPY.problem, COPY.openFor]}
							rows={shown.map(row)}
						/>
						{items.length > SHOWN ? (
							<p className="text-xs text-muted">{COPY.more(formatNumber(items.length - SHOWN))}</p>
						) : null}
					</div>
				);
			}}
		</DataCard>
	);
}
