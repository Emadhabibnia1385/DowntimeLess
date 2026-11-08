import { StatCard } from "@nyxon/nasim";
import type { FleetTraffic } from "@/api/generated/model";
import { formatBytes, formatDate, formatNumber, t } from "@/strings";
import { dayStart, parseDay } from "../lib/period";
import { Split } from "./Split";

// Today, yesterday and the chosen period for the fleet or one server, download and upload split.
export function TrafficTiles({ scope }: { scope: FleetTraffic }) {
	const peak = scope.peak_day;
	const peakDay = peak ? parseDay(peak.date) : null;
	return (
		<section aria-label={t.traffic.tiles.label} className="grid grid-cols-2 gap-3 lg:grid-cols-5">
			<StatCard
				label={t.traffic.tiles.today}
				value={formatBytes(scope.today.total)}
				hint={<Split rx={scope.today.rx} tx={scope.today.tx} />}
			/>
			<StatCard
				label={t.traffic.tiles.yesterday}
				value={formatBytes(scope.yesterday.total)}
				hint={<Split rx={scope.yesterday.rx} tx={scope.yesterday.tx} />}
			/>
			<StatCard
				label={t.traffic.tiles.period}
				value={formatBytes(scope.period.total)}
				hint={<Split rx={scope.period.rx} tx={scope.period.tx} />}
			/>
			<StatCard
				label={t.traffic.tiles.average}
				value={formatBytes(scope.avg_per_day.total)}
				hint={t.traffic.tiles.activeDays(formatNumber(scope.active_days))}
			/>
			<StatCard
				className="col-span-2 lg:col-span-1"
				label={t.traffic.tiles.peak}
				value={peak ? formatBytes(peak.total) : t.common.none}
				hint={
					peak && peakDay !== null ? (
						<>
							<span className="block">{formatDate(dayStart(peakDay), "Asia/Tehran")}</span>
							<Split rx={peak.rx} tx={peak.tx} />
						</>
					) : (
						t.traffic.tiles.noPeak
					)
				}
			/>
		</section>
	);
}
