import { EmptyState, StaticTable, StatusChip } from "@nyxon/nasim";
import type { IssueSummary } from "@/api/generated/model";
import { issueLabel, ServerLabel, useHistory } from "@/features/issues";
import { useServers } from "@/features/servers";
import { flagOf, formatDuration, formatNumber, t } from "@/strings";
import { recurring } from "../lib/stats";
import { COMPACT_TABLE, DataCard } from "./DataCard";

const COPY = t.dashboard.recurring;
const SHOWN = 6;

// Problems that came and went more than once in the last 24 hours, the most often first.
export function RecurringCard() {
	const history = useHistory("24h");
	const servers = useServers();
	const flags = new Map((servers.data ?? []).map((server) => [server.id, flagOf(server.country)]));
	const row = (item: IssueSummary) => ({
		id: item.key,
		cells: [
			<ServerLabel
				key="server"
				serverId={item.server_id}
				name={item.server_name}
				flag={item.server_id === null ? "" : (flags.get(item.server_id) ?? "")}
			/>,
			<span key="title" className="block whitespace-normal text-sm">
				{issueLabel(item.code, item.title)}
			</span>,
			<span key="times" className="whitespace-nowrap font-semibold tabular-nums">
				{COPY.timesValue(formatNumber(item.occurrences))}
			</span>,
			<span key="total" className="tabular-nums">
				{formatDuration(item.total_s)}
			</span>,
			<StatusChip
				key="state"
				tone={item.active_now ? "warning" : "success"}
				label={item.active_now ? COPY.now : COPY.gone}
				size="sm"
			/>,
		],
	});
	return (
		<DataCard
			title={COPY.title}
			description={COPY.subtitle}
			href="/issues?tab=history"
			linkLabel={t.dashboard.issues.all}
			query={history}
		>
			{(data) => {
				const rows = recurring(data.summary).slice(0, SHOWN);
				if (rows.length === 0) {
					return <EmptyState title={COPY.emptyTitle} description={COPY.empty} />;
				}
				return (
					<StaticTable
						caption={COPY.tableLabel}
						className={COMPACT_TABLE}
						columns={[
							COPY.server,
							COPY.problem,
							COPY.times,
							COPY.total,
							t.issueHistory.columns.state,
						]}
						rows={rows.map(row)}
					/>
				);
			}}
		</DataCard>
	);
}
