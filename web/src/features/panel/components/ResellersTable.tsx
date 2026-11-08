import { Button, type DataColumn, DataTable, StatusChip } from "@nyxon/nasim";
import { useState } from "react";
import type { Reseller } from "@/api/generated/model";
import { formatBytes, formatDecimal, formatPercent, t } from "@/strings";
import {
	DEFAULT_RESELLER_SORT,
	levelTone,
	nextSort,
	type ResellerKey,
	type ResellerSort,
	sortResellers,
} from "../lib/view";

const R = t.panel.resellers;
const LEVELS: Record<string, string> = R.levels;
const BAR = { danger: "bg-danger", warning: "bg-warning", success: "bg-accent" } as const;

function Head({
	label,
	sortKey,
	sort,
	onSort,
}: {
	label: string;
	sortKey: ResellerKey;
	sort: ResellerSort;
	onSort: (key: ResellerKey) => void;
}) {
	const active = sort.key === sortKey ? sort.direction : null;
	return (
		<Button
			variant="ghost"
			size="sm"
			aria-label={R.sortBy(label)}
			onPress={() => onSort(sortKey)}
			className="h-auto min-h-0 gap-1 rounded px-1 py-0.5 font-semibold"
		>
			{label}
			<span aria-hidden className={active ? "text-accent" : "text-muted opacity-50"}>
				{active === "asc" ? "▲" : active === "desc" ? "▼" : "↕"}
			</span>
		</Button>
	);
}

function Bar({ row }: { row: Reseller }) {
	const tone = levelTone(row.level) as keyof typeof BAR;
	const width = Math.max(2, Math.min(100, row.used_pct));
	return (
		<div className="flex items-center gap-2">
			<div
				aria-hidden
				className="h-2 w-24 shrink-0 overflow-hidden rounded-full bg-surface-tertiary"
			>
				<div className={`h-full rounded-full ${BAR[tone]}`} style={{ width: `${width}%` }} />
			</div>
			<span className="tabular-nums">{formatPercent(row.used_pct)}</span>
		</div>
	);
}

function HoursLeft({ row }: { row: Reseller }) {
	if (row.used >= row.limit) return <StatusChip tone="danger" label={R.finished} size="sm" />;
	if (row.hours_left == null) return <span className="text-xs text-muted">{R.noBurn}</span>;
	return <span className="tabular-nums">{R.hours(formatDecimal(row.hours_left, 1))}</span>;
}

// Resellers with a limit: used, limit, a share bar and hours left at the last hour's burn.
export function ResellersTable({ rows }: { rows: readonly Reseller[] }) {
	const [sort, setSort] = useState<ResellerSort>(DEFAULT_RESELLER_SORT);
	const onSort = (key: ResellerKey) => setSort((current) => nextSort(current, key));
	const head = (label: string, key: ResellerKey) => (
		<Head label={label} sortKey={key} sort={sort} onSort={onSort} />
	);
	const columns: DataColumn<Reseller>[] = [
		{
			id: "name",
			header: head(R.columns.name, "name"),
			isRowHeader: true,
			cell: (row) => (
				<div className="flex flex-wrap items-center gap-2">
					<span dir="ltr" className="font-medium">
						{row.name}
					</span>
					{row.level !== "ok" ? (
						<StatusChip
							tone={levelTone(row.level)}
							label={LEVELS[row.level] ?? row.level}
							size="sm"
						/>
					) : null}
				</div>
			),
		},
		{
			id: "used",
			header: head(R.columns.used, "used"),
			align: "end",
			cell: (row) => <span className="tabular-nums">{formatBytes(row.used)}</span>,
		},
		{
			id: "limit",
			header: head(R.columns.limit, "limit"),
			align: "end",
			cell: (row) => <span className="tabular-nums">{formatBytes(row.limit)}</span>,
		},
		{ id: "percent", header: head(R.columns.percent, "percent"), cell: (row) => <Bar row={row} /> },
		{
			id: "hours",
			header: head(R.columns.hoursLeft, "hours"),
			cell: (row) => <HoursLeft row={row} />,
		},
	];
	return (
		<DataTable
			ariaLabel={R.tableLabel}
			columns={columns}
			rows={sortResellers(rows, sort)}
			getRowId={(row) => row.name}
			status="ready"
			emptyTitle={R.empty}
		/>
	);
}
