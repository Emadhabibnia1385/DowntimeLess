import { formatDateTime, t } from "@/strings";
import type { ChartSeries } from "./types";

/** The point in one line, for a screen reader: the time, then each series' value. */
export function pointText(
	time: number,
	index: number,
	series: readonly ChartSeries[],
	format: (value: number) => string,
): string {
	const values = series.map((item) => {
		const value = item.values[index];
		return `${item.label} ${value == null ? t.common.none : (item.format ?? format)(value)}`;
	});
	return [formatDateTime(time), ...values].join("، ");
}
