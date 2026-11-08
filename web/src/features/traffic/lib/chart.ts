import type { HourProfile, TrafficPoint } from "@/api/generated/model";
import type { ChartSeries } from "@/shared/charts/types";
import { formatBytes, formatDecimal, t } from "@/strings";

const UNITS = [
	t.units.byte,
	t.units.kilobyte,
	t.units.megabyte,
	t.units.gigabyte,
	t.units.terabyte,
];

/** The unit that keeps the biggest value between 1 and 1024: its divisor and name. */
export function pickUnit(maxBytes: number): { divisor: number; name: string } {
	let step = 0;
	while (maxBytes / 1024 ** (step + 1) >= 1 && step < UNITS.length - 1) step += 1;
	return { divisor: 1024 ** step, name: UNITS[step] ?? t.units.byte };
}

export type TrafficChart = {
	times: number[];
	series: ChartSeries[];
	format: (value: number) => string;
	axisFormat: (value: number) => string;
	unit: string;
};

/** Download and upload as two lines in one unit, so the axis reads 0, 50, 100 and not 47.7. */
export function buildTrafficChart(points: readonly TrafficPoint[]): TrafficChart {
	const biggest = Math.max(0, ...points.flatMap((point) => [point.rx, point.tx]));
	const { divisor, name } = pickUnit(biggest);
	return {
		times: points.map((point) => point.ts),
		series: [
			{
				key: "rx",
				label: t.traffic.download,
				tone: "accent",
				area: true,
				values: points.map((point) => point.rx / divisor),
			},
			{
				key: "tx",
				label: t.traffic.upload,
				tone: "info",
				values: points.map((point) => point.tx / divisor),
			},
		],
		format: (value) => formatBytes(value * divisor),
		axisFormat: (value) => formatDecimal(value, 1),
		unit: t.traffic.chart.unit(name),
	};
}

/** The busiest hour of the day (by download plus upload), or null when nothing was moved. */
export function busiestHour(profile: readonly HourProfile[]): HourProfile | null {
	let best: HourProfile | null = null;
	for (const entry of profile) {
		if (entry.rx + entry.tx > (best ? best.rx + best.tx : 0)) best = entry;
	}
	return best;
}
