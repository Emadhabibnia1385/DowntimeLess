import { LinkButton, SectionCard } from "@nyxon/nasim";
import { Link } from "@tanstack/react-router";
import { useOverviewPingMatrix } from "@/api/generated/overview/overview";
import { HealthChip, healthOf, numberOrNull, type Thresholds } from "@/features/ping-matrix";
import { useThresholds } from "@/features/settings";
import { formatMs, formatPercent, t } from "@/strings";

// For a relay: the ping from it to every foreign server; hidden when nothing was measured.
export function RelayPingCard({ serverId }: { serverId: number }) {
	const matrix = useOverviewPingMatrix({ query: { refetchInterval: 30_000 } });
	const limits = useThresholds() as Thresholds;
	const rows = (matrix.data ?? [])
		.filter((cell) => cell.from_id === serverId)
		.sort((a, b) => a.to_name.localeCompare(b.to_name));
	if (rows.length === 0) return null;
	return (
		<SectionCard
			title={t.server.relayPingTitle}
			actions={
				<LinkButton href="/ping-matrix" size="sm" variant="secondary">
					{t.server.relayPingAll}
				</LinkButton>
			}
		>
			<ul className="flex flex-col divide-y divide-separator">
				{rows.map((cell) => {
					const loss = numberOrNull(cell.loss_pct);
					const rtt = numberOrNull(cell.rtt_ms);
					const to = numberOrNull(cell.to_id);
					return (
						<li key={cell.target} className="flex items-center justify-between gap-3 py-2">
							<div className="min-w-0">
								{to === null ? (
									<span className="text-sm font-medium">{cell.to_name}</span>
								) : (
									<Link
										to="/servers/$serverId"
										params={{ serverId: String(to) }}
										className="text-sm font-medium text-accent-soft-foreground underline-offset-4 hover:underline"
									>
										{cell.to_name}
									</Link>
								)}
								{loss === null ? null : (
									<p className="text-xs text-muted">
										{t.pingMatrix.cell(
											formatPercent(loss),
											rtt === null ? t.common.none : formatMs(rtt),
										)}
									</p>
								)}
							</div>
							<HealthChip health={healthOf(loss, limits)} />
						</li>
					);
				})}
			</ul>
		</SectionCard>
	);
}
