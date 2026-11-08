import { StaticTable } from "@nyxon/nasim";
import { formatDateTime, t } from "@/strings";
import type { ChartSeries } from "./types";

// The same data as the lines, newest first, with the exact values in text.
export function ChartTable({
	title,
	times,
	series,
	format,
}: {
	title: string;
	times: readonly number[];
	series: readonly ChartSeries[];
	format: (value: number) => string;
}) {
	const order = times.map((_, index) => times.length - 1 - index);
	return (
		<div className="max-h-96 overflow-auto rounded-xl">
			<StaticTable
				caption={t.chart.tableLabel(title)}
				columns={[t.chart.time, ...series.map((item) => item.label)]}
				rows={order.map((index) => ({
					id: String(times[index]),
					cells: [
						formatDateTime(times[index] ?? 0),
						...series.map((item) => {
							const value = item.values[index];
							return value == null ? t.common.none : (item.format ?? format)(value);
						}),
					],
				}))}
			/>
		</div>
	);
}
