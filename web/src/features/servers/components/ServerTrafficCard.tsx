import { KeyValueList, SectionCard, SkeletonRows } from "@nyxon/nasim";
import { Link } from "@tanstack/react-router";
import { useTrafficSummary } from "@/api/generated/traffic/traffic";
import { Loadable } from "@/shared/Loadable";
import { formatBytes, formatDate, t } from "@/strings";

const size = (volume: { total: number; rx: number; tx: number }, date?: string) => (
	<div className="leading-tight">
		<p className="font-semibold">{formatBytes(volume.total)}</p>
		<p className="text-xs text-muted">
			{date ? `${date} · ` : ""}
			{t.traffic.card.split(formatBytes(volume.rx), formatBytes(volume.tx))}
		</p>
	</div>
);

// Today, yesterday, the last 30 days and the peak day of one server, with a link to the details.
export function ServerTrafficCard({ serverId }: { serverId: number }) {
	const summary = useTrafficSummary({}, { query: { refetchInterval: 60_000 } });
	return (
		<SectionCard title={t.traffic.card.title} level={3}>
			<Loadable query={summary} skeleton={<SkeletonRows rows={2} dense />}>
				{(data) => {
					const row = data.servers.find((server) => server.server_id === serverId);
					if (!row) return <p className="text-sm text-muted">{t.chart.empty}</p>;
					const peak = row.peak_day;
					return (
						<div className="flex flex-col gap-4">
							<KeyValueList
								layout="stacked"
								items={[
									{ label: t.traffic.card.today, value: size(row.today) },
									{ label: t.traffic.card.yesterday, value: size(row.yesterday) },
									{ label: t.traffic.card.period, value: size(row.period) },
									{
										label: t.traffic.card.peak,
										value: peak
											? size(peak, formatDate(Date.parse(`${peak.date}T00:00:00Z`) / 1000, "UTC"))
											: t.common.none,
									},
								]}
							/>
							<Link
								to="/traffic"
								search={{ server: serverId }}
								className="text-sm font-semibold text-accent-soft-foreground underline-offset-4 hover:underline"
							>
								{t.traffic.card.details}
							</Link>
						</div>
					);
				}}
			</Loadable>
		</SectionCard>
	);
}
