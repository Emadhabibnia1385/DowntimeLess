import { Button, ConfirmDialog, type DataColumn, DataTable, StatusChip, toast } from "@nyxon/nasim";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import type { SslRow } from "@/api/generated/model";
import { useSslCheckDomain, useSslDeleteDomain } from "@/api/generated/ssl/ssl";
import { errorMessage } from "@/api/transport";
import { RefreshIcon, TrashIcon } from "@/shared/icons";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { formatDate, formatDateTime, t } from "@/strings";
import { useSsl } from "../api";
import { autoRenewStatus, certStatus } from "../lib/status";

const probeId = (row: SslRow): number | null => (row.kind === "probe" ? (row.id ?? null) : null);

function NameCell({ row }: { row: SslRow }) {
	const others = row.domains.filter((domain) => domain !== row.name);
	return (
		<div className="flex flex-col items-start gap-1">
			<span dir="ltr" className="font-mono">
				{row.name}
			</span>
			{others.length > 0 ? (
				<span dir="ltr" className="font-mono text-xs text-muted">
					{others.join(", ")}
				</span>
			) : null}
		</div>
	);
}

function WhereCell({ row }: { row: SslRow }) {
	if (row.kind !== "file" || row.server_id === null) return t.ssl.fromOutside;
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

function StatusCell({ row }: { row: SslRow }) {
	const status = certStatus(row);
	return <StatusChip tone={status.tone} label={status.label} size="sm" />;
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

function DetailsCell({ row }: { row: SslRow }) {
	const lines = [
		row.issuer ? `${t.ssl.issuer}: ${row.issuer}` : null,
		row.checked_at !== null && row.kind === "probe"
			? `${t.ssl.checkedAt}: ${formatDateTime(row.checked_at)}`
			: null,
		row.note || null,
	].filter((line): line is string => line !== null);
	if (lines.length === 0 && !row.error && !row.stale) return t.common.none;
	return (
		<div className="flex flex-col gap-1 text-sm">
			{lines.map((line) => (
				<span key={line}>{line}</span>
			))}
			{row.error ? <span className="text-danger">{row.error}</span> : null}
			{row.stale ? <span className="text-muted">{t.ssl.stale}</span> : null}
		</div>
	);
}

// Certificates found by agents and domains probed from outside; only probes can be changed here.
export function CertTable({ canManage }: { canManage: boolean }) {
	const certs = useSsl();
	const refresh = useRefreshAll();
	const [removing, setRemoving] = useState<SslRow | null>(null);
	const check = useSslCheckDomain({
		mutation: {
			onSuccess: () => {
				toast.success(t.ssl.rechecked);
				void refresh();
			},
			onError: (error) => toast.danger(errorMessage(error)),
		},
	});
	const remove = useSslDeleteDomain({
		mutation: {
			onSuccess: () => {
				setRemoving(null);
				void refresh();
			},
			onError: (error) => {
				setRemoving(null);
				toast.danger(errorMessage(error));
			},
		},
	});
	const columns: DataColumn<SslRow>[] = [
		{ id: "name", header: t.ssl.name, isRowHeader: true, cell: (row) => <NameCell row={row} /> },
		{ id: "where", header: t.ssl.where, cell: (row) => <WhereCell row={row} /> },
		{ id: "status", header: t.ssl.status, cell: (row) => <StatusCell row={row} /> },
		{
			id: "expiry",
			header: t.ssl.expiry,
			cell: (row) => (row.not_after === null ? t.common.none : formatDate(row.not_after)),
		},
		{ id: "renew", header: t.ssl.autoRenew, cell: (row) => <RenewCell row={row} /> },
		{ id: "details", header: t.ssl.details, cell: (row) => <DetailsCell row={row} /> },
		{
			id: "actions",
			header: t.ssl.actions,
			isActions: true,
			cell: (row) => {
				const id = probeId(row);
				if (id === null || !canManage) return null;
				return (
					<div className="flex flex-wrap gap-2">
						<Button
							size="sm"
							variant="secondary"
							isPending={check.isPending && check.variables?.domainId === id}
							onPress={() => check.mutate({ domainId: id })}
						>
							<RefreshIcon aria-hidden />
							{t.ssl.recheck}
						</Button>
						<Button size="sm" variant="danger-soft" onPress={() => setRemoving(row)}>
							<TrashIcon aria-hidden />
							{t.common.delete}
						</Button>
					</div>
				);
			},
		},
	];
	return (
		<>
			<DataTable
				ariaLabel={t.ssl.tableLabel}
				columns={columns}
				rows={certs.data}
				getRowId={(row) => row.key}
				status={certs.isPending ? "loading" : certs.isError ? "error" : "ready"}
				onRetry={() => void certs.refetch()}
				emptyTitle={t.ssl.emptyTitle}
				empty={t.ssl.empty}
				cards="md"
			/>
			<ConfirmDialog
				isOpen={removing !== null}
				onOpenChange={(open) => !open && setRemoving(null)}
				tone="danger"
				title={t.ssl.deleteTitle}
				description={t.ssl.deleteBody}
				confirmLabel={t.common.delete}
				isPending={remove.isPending}
				onConfirm={() => {
					const id = removing ? probeId(removing) : null;
					if (id !== null) remove.mutate({ domainId: id });
				}}
			/>
		</>
	);
}
