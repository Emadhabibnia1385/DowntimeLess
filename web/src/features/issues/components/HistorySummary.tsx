import { Button, type DataColumn, DataTable, StatusChip } from "@nyxon/nasim";
import type { IssueSummary } from "@/api/generated/model";
import { formatDateTime, formatDuration, formatNumber, formatRelativeTime, t } from "@/strings";
import { issueLabel, nextSort, severityTone, type SortKey, type SortState } from "../lib/history";
import { ServerLabel } from "./ServerLabel";

const SEVERITIES: Record<string, string> = t.severity;
const COLUMNS = t.issueHistory.columns;

function SortHeader({
	label,
	sortKey,
	sort,
	onSort,
}: {
	label: string;
	sortKey: SortKey;
	sort: SortState;
	onSort: (next: SortState) => void;
}) {
	const active = sort?.key === sortKey ? sort.direction : null;
	return (
		<Button
			variant="ghost"
			size="sm"
			aria-label={t.issueHistory.sortBy(label)}
			onPress={() => onSort(nextSort(sort, sortKey))}
			className="h-auto min-h-0 gap-1 rounded px-1 py-0.5 text-xs font-medium text-inherit"
		>
			{label}
			<span aria-hidden className={active ? "text-accent" : "text-muted opacity-50"}>
				{active === "asc" ? "▲" : active === "desc" ? "▼" : "↕"}
			</span>
		</Button>
	);
}

// One row per issue on a server: how often, how long in total, when last, still on or not.
export function HistorySummary({
	rows,
	flags,
	sort,
	onSort,
	filtered,
}: {
	rows: readonly IssueSummary[];
	flags: ReadonlyMap<number, string>;
	sort: SortState;
	onSort: (next: SortState) => void;
	filtered: boolean;
}) {
	const head = (label: string, key: SortKey) => (
		<SortHeader label={label} sortKey={key} sort={sort} onSort={onSort} />
	);
	const columns: DataColumn<IssueSummary>[] = [
		{
			id: "server",
			header: COLUMNS.server,
			isRowHeader: true,
			cell: (row) => (
				<ServerLabel
					serverId={row.server_id}
					name={row.server_name}
					flag={row.server_id === null ? "" : (flags.get(row.server_id) ?? "")}
				/>
			),
		},
		{
			id: "issue",
			header: COLUMNS.issue,
			cell: (row) => (
				<span className="block max-w-96 whitespace-normal text-sm">
					{issueLabel(row.code, row.title)}
				</span>
			),
		},
		{
			id: "severity",
			header: COLUMNS.severity,
			cell: (row) => (
				<StatusChip
					tone={severityTone(row.severity)}
					label={SEVERITIES[row.severity] ?? row.severity}
					size="sm"
				/>
			),
		},
		{
			id: "occurrences",
			header: head(COLUMNS.occurrences, "occurrences"),
			cell: (row) => (
				<div className="flex items-center gap-2">
					<span className="tabular-nums font-semibold">{formatNumber(row.occurrences)}</span>
					{row.flapping ? (
						<StatusChip tone="warning" label={t.issueHistory.flapping} size="sm" />
					) : null}
				</div>
			),
		},
		{
			id: "total",
			header: head(COLUMNS.total, "total"),
			cell: (row) => <span className="tabular-nums">{formatDuration(row.total_s)}</span>,
		},
		{
			id: "last",
			header: head(COLUMNS.last, "last"),
			cell: (row) => (
				<span title={formatDateTime(row.last_at)} className="text-sm text-muted">
					{formatRelativeTime(row.last_at)}
				</span>
			),
		},
		{
			id: "state",
			header: COLUMNS.state,
			cell: (row) => (
				<StatusChip
					tone={row.active_now ? "warning" : "success"}
					label={row.active_now ? t.issueHistory.active : t.issueHistory.resolved}
					size="sm"
				/>
			),
		},
	];
	return (
		<DataTable<IssueSummary>
			ariaLabel={t.issueHistory.summaryLabel}
			columns={columns}
			rows={rows}
			getRowId={(row) => row.key}
			status="ready"
			emptyTitle={filtered ? t.issueHistory.noMatchTitle : t.issueHistory.emptyTitle}
			empty={filtered ? t.issueHistory.noMatch : t.issueHistory.empty}
		/>
	);
}
