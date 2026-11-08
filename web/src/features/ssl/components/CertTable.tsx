import { type DataColumn, DataTable, StatusChip } from "@nyxon/nasim";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import type { SslRow } from "@/api/generated/model";
import { formatDate, t } from "@/strings";
import { useSsl } from "../api";
import { autoRenewStatus, certStatus } from "../lib/status";
import {
	DEFAULT_SORT,
	filterRows,
	nextSort,
	type SortKey,
	type SortState,
	sortRows,
	type StatusFilter,
} from "../lib/view";
import { RowActions } from "./RowActions";
import { SortHead } from "./SortHead";
import { SslToolbar } from "./SslToolbar";

function NameCell({ row }: { row: SslRow }) {
	const others = row.domains.filter((domain) => domain !== row.name);
	return (
		<div className="flex flex-col items-start gap-1">
			<div className="flex flex-wrap items-center gap-2">
				<span dir="ltr" className="font-mono">
					{row.name}
				</span>
				{row.auto ? (
					<span title={t.ssl.discoveredHint}>
						<StatusChip tone="info" label={t.ssl.discovered} size="sm" />
					</span>
				) : null}
			</div>
			{others.length > 0 ? (
				<span dir="ltr" className="font-mono text-xs text-muted">
					{others.join(", ")}
				</span>
			) : null}
			{row.issuer ? (
				<span className="text-xs text-muted">{`${t.ssl.issuer}: ${row.issuer}`}</span>
			) : null}
			{row.error ? <span className="text-xs text-danger">{row.error}</span> : null}
			{row.stale ? <span className="text-xs text-muted">{t.ssl.stale}</span> : null}
			{row.note ? <span className="text-xs text-muted">{row.note}</span> : null}
		</div>
	);
}

function WhereCell({ row }: { row: SslRow }) {
	if (row.server_id === null) return t.ssl.fromOutside;
	return (
		<Link
			to="/servers/$serverId"
			params={{ serverId: String(row.server_id) }}
			className="text-accent-soft-foreground underline-offset-4 hover:underline"
		>
			{t.ssl.onServer(row.server_name ?? String(row.server_id))}
		</Link>
	);
}

function RenewCell({ row }: { row: SslRow }) {
	const renew = autoRenewStatus(row.auto_renew);
	return (
		<div className="flex flex-wrap gap-1.5">
			<StatusChip tone={renew.tone} label={renew.label} size="sm" />
			{row.renew_failed ? <StatusChip tone="danger" label={t.ssl.renewFailed} size="sm" /> : null}
		</div>
	);
}

// Certificates agents found, domains they found in web server configs, and domains added by hand.
export function CertTable({ canManage }: { canManage: boolean }) {
	const certs = useSsl();
	const [sort, setSort] = useState<SortState>(DEFAULT_SORT);
	const [status, setStatus] = useState<StatusFilter>("all");
	const [query, setQuery] = useState("");
	const all = certs.data ?? [];
	const rows = sortRows(filterRows(all, status, query), sort);
	const filtered = all.length > 0;
	const onSort = (key: SortKey) => setSort((current) => nextSort(current, key));
	const head = (label: string, key: SortKey) => (
		<SortHead label={label} sortKey={key} sort={sort} onSort={onSort} />
	);
	const columns: DataColumn<SslRow>[] = [
		{
			id: "name",
			header: head(t.ssl.name, "name"),
			isRowHeader: true,
			cell: (row) => <NameCell row={row} />,
		},
		{ id: "where", header: head(t.ssl.where, "where"), cell: (row) => <WhereCell row={row} /> },
		{
			id: "status",
			header: head(t.ssl.status, "status"),
			cell: (row) => {
				const state = certStatus(row);
				return <StatusChip tone={state.tone} label={state.label} size="sm" />;
			},
		},
		{
			id: "expiry",
			header: head(t.ssl.expiry, "expiry"),
			cell: (row) => (row.not_after === null ? t.common.none : formatDate(row.not_after)),
		},
		{ id: "renew", header: head(t.ssl.autoRenew, "renew"), cell: (row) => <RenewCell row={row} /> },
		...(canManage
			? [
					{
						id: "actions",
						header: t.ssl.actions,
						isActions: true,
						cell: (row: SslRow) => <RowActions row={row} />,
					},
				]
			: []),
	];
	return (
		<div className="flex flex-col gap-4">
			<SslToolbar status={status} onStatus={setStatus} query={query} onQuery={setQuery} />
			<DataTable
				ariaLabel={t.ssl.tableLabel}
				columns={columns}
				rows={rows}
				getRowId={(row) => row.key}
				status={certs.isPending ? "loading" : certs.isError ? "error" : "ready"}
				onRetry={() => void certs.refetch()}
				emptyTitle={filtered ? t.ssl.noResults : t.ssl.emptyTitle}
				empty={filtered ? undefined : t.ssl.empty}
			/>
		</div>
	);
}
