import { t } from "@/strings";
import { timeText } from "./timeText";
import type { ChartSeries, ChartTime } from "./types";

/** The point in one line, for a screen reader: the time, then each series' value. */
export function pointText(
	moment: number,
	index: number,
	series: readonly ChartSeries[],
	format: (value: number) => string,
	time?: ChartTime,
): string {
	const values = series.map((item) => {
		const value = item.values[index];
		return `${item.label} ${value == null ? t.common.none : (item.format ?? format)(value)}`;
	});
	return [timeText(moment, time), ...values].join("، ");
}
