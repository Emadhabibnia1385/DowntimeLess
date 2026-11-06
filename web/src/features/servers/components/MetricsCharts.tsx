import { ColumnChart, ErrorState, FilterChips, SectionCard, Spinner } from "@nyxon/nasim";
import type { MetricPoint } from "@/api/generated/model";
import { useServersMetrics } from "@/api/generated/servers/servers";
import { errorMessage } from "@/api/transport";
import { formatBytes, formatDateTime, formatNumber, formatPercent, formatTick, t } from "@/strings";
import { bucketSamples, peakOf, RANGES, type Range } from "../lib/chart";

type Metric = {
	key: string;
	title: string;
	pick: (point: MetricPoint) => number | null;
	mode: "mean" | "sum";
	format: (value: number) => string;
	tone: "accent" | "success" | "info";
};

const METRICS: Metric[] = [
	{
		key: "cpu",
		title: t.server.chartCpu,
		pick: (p) => p.cpu,
		mode: "mean",
		format: formatPercent,
		tone: "accent",
	},
	{
		key: "ram",
		title: t.server.chartRam,
		pick: (p) => p.ram_pct,
		mode: "mean",
		format: formatPercent,
		tone: "accent",
	},
	{
		key: "disk",
		title: t.server.chartDisk,
		pick: (p) => p.disk_pct,
		mode: "mean",
		format: formatPercent,
		tone: "info",
	},
	{
		key: "rx",
		title: t.server.chartRx,
		pick: (p) => p.rx_bytes,
		mode: "sum",
		format: formatBytes,
		tone: "success",
	},
	{
		key: "tx",
		title: t.server.chartTx,
		pick: (p) => p.tx_bytes,
		mode: "sum",
		format: formatBytes,
		tone: "info",
	},
];

const rangeOptions = (Object.keys(RANGES) as Range[]).map((value) => ({
	value,
	label: t.server.ranges[value],
}));

function Chart({ metric, points, span }: { metric: Metric; points: MetricPoint[]; span: number }) {
	const bars = bucketSamples(
		points.map((point) => ({ ts: point.ts, value: metric.pick(point) })),
		metric.mode,
	);
	const peak = peakOf(bars);
	const total = metric.mode === "sum" ? bars.reduce((sum, bar) => sum + (bar.value ?? 0), 0) : null;
	const summary = `${t.server.chartSummary(formatNumber(bars.length), metric.format(peak))}${
		total === null ? "" : t.server.chartTotal(metric.format(total))
	}`;
	return (
		<ColumnChart
			title={metric.title}
			tone={metric.tone}
			summary={summary}
			showSummary
			empty={t.server.chartNoData}
			note={t.server.chartNote}
			points={bars.map((bar) => ({
				key: String(bar.ts),
				label: formatTick(bar.ts, span),
				value: bar.value ?? 0,
				tooltip: `${formatDateTime(bar.ts)}: ${bar.value === null ? t.common.none : metric.format(bar.value)}`,
			}))}
			table={{
				showLabel: t.server.chartTable,
				label: `${t.server.chartTableLabel}: ${metric.title}`,
				columns: [t.server.chartTime, t.server.chartValue],
				rows: bars.map((bar) => ({
					key: String(bar.ts),
					cells: [
						formatDateTime(bar.ts),
						bar.value === null ? t.common.none : metric.format(bar.value),
					],
				})),
			}}
		/>
	);
}

// CPU, RAM, disk and traffic over a range chosen with the chips (kept in the address by the page).
export function MetricsCharts({
	serverId,
	range,
	onRangeChange,
}: {
	serverId: number;
	range: Range;
	onRangeChange: (range: Range) => void;
}) {
	const metrics = useServersMetrics(serverId, { range }, { query: { refetchInterval: 60_000 } });
	return (
		<SectionCard title={t.server.charts}>
			<div className="flex flex-col gap-6">
				<FilterChips
					label={t.server.range}
					value={range}
					onChange={(value) => onRangeChange(value as Range)}
					options={rangeOptions}
				/>
				{metrics.isPending ? (
					<Spinner />
				) : metrics.isError ? (
					<ErrorState
						message={errorMessage(metrics.error)}
						onRetry={() => void metrics.refetch()}
					/>
				) : (
					<div className="grid gap-6 xl:grid-cols-2">
						{METRICS.map((metric) => (
							<Chart
								key={metric.key}
								metric={metric}
								points={metrics.data.points}
								span={RANGES[range]}
							/>
						))}
					</div>
				)}
			</div>
		</SectionCard>
	);
}
