import { EmptyState, PageHeader, StaticTable, StatusChip } from "@nyxon/nasim";
import { Link } from "@tanstack/react-router";
import type { PingCell } from "@/api/generated/model";
import { useOverviewPingMatrix } from "@/api/generated/overview/overview";
import { useServers } from "@/features/servers";
import { useThresholds } from "@/features/settings";
import { IpText } from "@/shared/IpText";
import { Loadable } from "@/shared/Loadable";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { flagOf, formatMs, formatPercent, t } from "@/strings";
import { buildMatrix, type Health, healthOf, numberOrNull, type Thresholds } from "../lib/matrix";

const TONES = { ok: "success", degraded: "warning", down: "danger", unknown: "neutral" } as const;
const LABELS: Record<Health, string> = {
	ok: t.pingMatrix.ok,
	degraded: t.pingMatrix.degraded,
	down: t.pingMatrix.down,
	unknown: t.pingMatrix.unknown,
};

function Cell({ cell, limits }: { cell: PingCell | undefined; limits: Thresholds }) {
	if (!cell) return <span aria-hidden>{t.pingMatrix.noCell}</span>;
	const loss = numberOrNull(cell.loss_pct);
	const rtt = numberOrNull(cell.rtt_ms);
	const health = healthOf(loss, limits);
	return (
		<div className="flex flex-col items-start gap-1">
			<StatusChip tone={TONES[health]} label={LABELS[health]} size="sm" />
			{loss === null ? null : (
				<span className="text-xs text-muted">
					{t.pingMatrix.cell(formatPercent(loss), rtt === null ? t.common.none : formatMs(rtt))}
				</span>
			)}
		</div>
	);
}

export function PingMatrixPage() {
	useDocumentTitle(t.pingMatrix.title);
	const matrix = useOverviewPingMatrix({ query: { refetchInterval: 30_000 } });
	const limits = useThresholds() as Thresholds;
	const servers = useServers();
	const countryOf = new Map((servers.data ?? []).map((server) => [server.id, server.country]));
	return (
		<div className="flex flex-col gap-6">
			<PageHeader title={t.pingMatrix.title} description={t.pingMatrix.subtitle} />
			<Loadable query={matrix}>
				{(cells) => {
					if (cells.length === 0) {
						return <EmptyState title={t.pingMatrix.emptyTitle} description={t.pingMatrix.empty} />;
					}
					const grid = buildMatrix(cells);
					return (
						<StaticTable
							caption={t.pingMatrix.tableLabel}
							className="min-w-[32rem]"
							columns={[
								t.pingMatrix.foreignServer,
								...grid.columns.map((column) => (
									<span key={column.key} className="flex flex-col">
										<span>
											<span aria-hidden>{flagOf("IR")}</span> {column.name}
										</span>
										<span className="text-xs font-normal text-muted">{t.pingMatrix.iranRelay}</span>
									</span>
								)),
							]}
							rows={grid.rows.map((row) => ({
								id: String(row.id),
								cells: [
									<div key="name" className="flex flex-col">
										<Link
											to="/servers/$serverId"
											params={{ serverId: String(row.id) }}
											className="font-semibold text-accent-soft-foreground underline-offset-4 hover:underline"
										>
											<span aria-hidden>{flagOf(countryOf.get(row.id))}</span> {row.name}
										</Link>
										<IpText ip={row.target} className="text-xs text-muted" />
									</div>,
									...grid.columns.map((column) => (
										<Cell key={column.key} cell={grid.cell(row.id, column.key)} limits={limits} />
									)),
								],
							}))}
						/>
					);
				}}
			</Loadable>
		</div>
	);
}
