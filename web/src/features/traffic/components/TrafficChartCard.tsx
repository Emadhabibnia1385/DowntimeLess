import { SectionCard } from "@nyxon/nasim";
import type { TrafficSeries } from "@/api/generated/model";
import { LineChart } from "@/shared/charts/LineChart";
import { t } from "@/strings";
import { buildTrafficChart } from "../lib/chart";

const DAY = 86_400;

// Download and upload over the period: hourly for a few days, daily for longer, in Tehran time.
export function TrafficChartCard({ data, fileName }: { data: TrafficSeries; fileName: string }) {
	const daily = data.bucket_s >= DAY;
	const empty = data.rx_total + data.tx_total === 0;
	const chart = buildTrafficChart(empty ? [] : data.points);
	const first = chart.times[0] ?? 0;
	const last = chart.times[chart.times.length - 1] ?? 0;
	return (
		<SectionCard
			title={t.traffic.chart.title}
			description={daily ? t.traffic.chart.perDay : t.traffic.chart.perHour}
		>
			<LineChart
				title={t.traffic.chart.title}
				hideTitle
				times={chart.times}
				series={chart.series}
				format={chart.format}
				axisFormat={chart.axisFormat}
				unit={chart.unit}
				spanSeconds={Math.max(last - first, 1)}
				fileName={fileName}
				time={{ dateOnly: daily, timeZone: "Asia/Tehran" }}
			/>
		</SectionCard>
	);
}
