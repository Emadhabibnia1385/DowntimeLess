import { useState } from "react";
import { t } from "@/strings";
import { ChartLegend } from "./ChartLegend";
import { ChartPlot } from "./ChartPlot";
import { ChartTable } from "./ChartTable";
import { ChartToolbar } from "./ChartToolbar";
import { downloadBlob } from "./download";
import { csvBlob, csvTime, toCsv } from "./lib";
import type { ChartSeries } from "./types";

export type LineChartProps = {
	/** Names the chart for screen readers, the table and, unless hidden, the heading. */
	title: string;
	hideTitle?: boolean;
	/** Epoch seconds, ascending; every series has one value per time. */
	times: readonly number[];
	series: readonly ChartSeries[];
	/** Values in the tooltip and the table; a series may bring its own. */
	format: (value: number) => string;
	/** Labels on the value axis; defaults to `format`. */
	axisFormat?: (value: number) => string;
	/** A fixed value range such as [0, 100] for percent. */
	domain?: readonly [number, number];
	/** The unit in words, shown above the axis. */
	unit?: string;
	/** The length of the range in seconds; picks the time labels. */
	spanSeconds: number;
	/** The CSV file's name without its extension. */
	fileName: string;
	height?: number;
};

const hasData = (series: readonly ChartSeries[]) =>
	series.some((item) => item.values.some((value) => value !== null));

// Series as lines over time: toggle chips, hover or arrow keys for values, a table and CSV.
export function LineChart({
	title,
	hideTitle,
	times,
	series,
	format,
	axisFormat,
	domain,
	unit,
	spanSeconds,
	fileName,
	height = 260,
}: LineChartProps) {
	const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());
	const [showTable, setShowTable] = useState(false);
	const shown = series.filter((item) => !hidden.has(item.key));
	const toggle = (key: string) =>
		setHidden((last) => {
			const next = new Set(last);
			if (next.has(key)) next.delete(key);
			else if (shown.length > 1) next.add(key);
			return next;
		});
	const download = () =>
		downloadBlob(
			csvBlob(
				toCsv(
					[t.chart.time, ...series.map((item) => item.label)],
					times.map((time, index) => [
						csvTime(time),
						...series.map((item) => item.values[index] ?? null),
					]),
				),
			),
			`${fileName}.csv`,
		);
	if (times.length === 0 || !hasData(series)) {
		return (
			<figure className="flex flex-col gap-2">
				{hideTitle ? null : <figcaption className="text-sm font-semibold">{title}</figcaption>}
				<p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted">
					{t.chart.empty}
				</p>
			</figure>
		);
	}
	return (
		<figure className="flex flex-col gap-3">
			{hideTitle ? null : <figcaption className="text-sm font-semibold">{title}</figcaption>}
			<div className="flex flex-wrap items-center justify-between gap-2">
				<ChartLegend label={t.chart.legend} series={series} hidden={hidden} onToggle={toggle} />
				<ChartToolbar
					showTable={showTable}
					onToggleView={() => setShowTable((last) => !last)}
					onDownload={download}
				/>
			</div>
			{showTable ? (
				<ChartTable title={title} times={times} series={series} format={format} />
			) : (
				<>
					{unit ? <p className="text-xs text-muted">{unit}</p> : null}
					<ChartPlot
						title={title}
						times={times}
						series={shown}
						format={format}
						axisFormat={axisFormat ?? format}
						domain={domain}
						spanSeconds={spanSeconds}
						height={height}
					/>
				</>
			)}
		</figure>
	);
}
