import type { MetricPoint } from "@/api/generated/model";
import { LineChart } from "@/shared/charts/LineChart";
import { buildHistory, type TabId } from "../lib/history";

// The charts of one tab; each keeps its own hidden series and table view while the range changes.
export function HistoryCharts({
	serverId,
	tab,
	range,
	spanSeconds,
	points,
	cores,
}: {
	serverId: number;
	tab: TabId;
	range: string;
	spanSeconds: number;
	points: readonly MetricPoint[];
	cores?: number | null;
}) {
	const history = buildHistory(tab, points, cores);
	return (
		<div className="flex flex-col gap-5">
			<p className="text-sm text-muted">{history.description}</p>
			{history.charts.map((chart, index) => (
				<LineChart
					key={`${tab}-${chart.key}`}
					title={chart.title}
					hideTitle={chart.hideTitle}
					times={history.times}
					series={chart.series}
					format={chart.format}
					axisFormat={chart.axisFormat}
					domain={chart.domain}
					unit={chart.unit}
					spanSeconds={spanSeconds}
					fileName={`server-${serverId}-${chart.key}-${range}`}
					height={index === 0 ? 260 : 170}
				/>
			))}
		</div>
	);
}
