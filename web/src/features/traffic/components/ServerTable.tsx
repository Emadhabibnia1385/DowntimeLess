import { type DataColumn, DataTable, SearchBox, SectionCard, SelectField } from "@nyxon/nasim";
import { Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import type { ServerTraffic } from "@/api/generated/model";
import { roleLabel, whereOf } from "@/features/servers";
import { formatBytes, formatDate, t } from "@/strings";
import { dayStart, parseDay } from "../lib/period";
import {
	filterRows,
	nextSort,
	serverLabel,
	type SortDirection,
	type SortKey,
	type SortState,
	sortRows,
} from "../lib/rows";
import { ShareBar } from "./ShareBar";
import { SortHead } from "./SortHead";

const ALL = "all";
const ROLE_ORDER = ["relay", "exit", "panel", "panel_only", "other"];

function NameCell({ row }: { row: ServerTraffic }) {
	const { flag } = whereOf({ role: row.role, country: row.country });
	return (
		<div className="flex items-center gap-2">
			<span aria-hidden className="text-2xl leading-none">
				{flag}
			</span>
			<div className="leading-tight">
				<Link
					to="/servers/$serverId"
					params={{ serverId: String(row.server_id) }}
					className="font-semibold text-accent-soft-foreground underline-offset-4 hover:underline"
				>
					{serverLabel(row)}
				</Link>
				<p className="text-xs text-muted">{roleLabel(row.role)}</p>
			</div>
		</div>
	);
}

function PeakCell({ row }: { row: ServerTraffic }) {
	const peak = row.peak_day;
	const day = peak ? parseDay(peak.date) : null;
	if (!peak || day === null) return t.common.none;
	return (
		<div className="leading-tight">
			<p>{formatBytes(peak.total)}</p>
			<p className="text-xs text-muted">{formatDate(dayStart(day), "Asia/Tehran")}</p>
		</div>
	);
}

// Every server's traffic for the period, sortable, with a name filter and a role filter.
export function ServerTable({
	rows,
	status,
	onRetry,
}: {
	rows: readonly ServerTraffic[] | undefined;
	status: "loading" | "error" | "ready";
	onRetry: () => void;
}) {
	const [sort, setSort] = useState<SortState>(null);
	const [text, setText] = useState("");
	const [roleChoice, setRoleChoice] = useState(ALL);
	const rolesPresent = ROLE_ORDER.filter((role) => (rows ?? []).some((row) => row.role === role));
	const roleOptions = [
		{ value: ALL, label: t.traffic.servers.roleAll },
		...rolesPresent.map((role) => ({ value: role, label: roleLabel(role) })),
	];
	const role = roleOptions.some((option) => option.value === roleChoice) ? roleChoice : ALL;
	const shown = useMemo(
		() => sortRows(filterRows(rows ?? [], text, role === ALL ? "" : role), sort),
		[rows, text, role, sort],
	);
	const onSort = (key: SortKey, first: SortDirection) =>
		setSort((current) => nextSort(current, key, first));
	const head = (label: string, key: SortKey, first: SortDirection = "desc") => (
		<SortHead label={label} sortKey={key} first={first} sort={sort} onSort={onSort} />
	);
	const s = t.traffic.servers;
	const columns: DataColumn<ServerTraffic>[] = [
		{
			id: "name",
			header: head(s.name, "name", "asc"),
			isRowHeader: true,
			align: "start",
			cell: (row) => <NameCell row={row} />,
		},
		{ id: "today", header: head(s.today, "today"), cell: (row) => formatBytes(row.today.total) },
		{
			id: "total",
			header: head(s.total, "total"),
			cell: (row) => <strong>{formatBytes(row.period.total)}</strong>,
		},
		{
			id: "rx",
			header: head(t.traffic.download, "rx"),
			cell: (row) => formatBytes(row.period.rx),
		},
		{
			id: "tx",
			header: head(t.traffic.upload, "tx"),
			cell: (row) => formatBytes(row.period.tx),
		},
		{
			id: "avg",
			header: head(s.average, "avg"),
			cell: (row) => (row.active_days ? formatBytes(row.avg_per_day.total) : t.common.none),
		},
		{ id: "peak", header: head(s.peak, "peak"), cell: (row) => <PeakCell row={row} /> },
		{
			id: "share",
			header: head(s.share, "share"),
			cell: (row) => <ShareBar percent={row.share_pct} />,
		},
	];
	return (
		<SectionCard title={s.title} description={s.description}>
			<div className="flex flex-col gap-4">
				<div className="grid max-w-xl items-end gap-3 sm:grid-cols-2">
					<SearchBox
						label={s.search}
						placeholder={s.searchPlaceholder}
						value={text}
						onChange={setText}
					/>
					<SelectField
						label={s.roleField}
						value={role}
						onChange={(next) => setRoleChoice(next ?? ALL)}
						options={roleOptions}
					/>
				</div>
				<DataTable
					ariaLabel={s.tableLabel}
					columns={columns.map((column) => ({
						...column,
						className: column.id === "name" ? "text-start" : "text-center",
					}))}
					rows={shown}
					getRowId={(row) => String(row.server_id)}
					status={status}
					onRetry={onRetry}
					emptyTitle={s.emptyTitle}
					empty={s.empty}
				/>
			</div>
		</SectionCard>
	);
}
