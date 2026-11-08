import { useRef } from "react";
import { t } from "@/strings";
import { ChartAxes } from "./ChartAxes";
import { ChartTooltip } from "./ChartTooltip";
import { Crosshair } from "./Crosshair";
import { pointText } from "./pointText";
import { gapLimit, makeXScale, nearestIndex, niceDomain } from "./lib";
import { SeriesLines } from "./SeriesLines";
import type { ChartSeries, ChartTime, PlotFrame } from "./types";
import { useElementBox } from "./useElementWidth";
import { useScrub } from "./useScrub";

const TOP = 10;
const BOTTOM = 24;
const EDGE = 6;

type PlotProps = {
	title: string;
	times: readonly number[];
	series: readonly ChartSeries[];
	format: (value: number) => string;
	axisFormat: (value: number) => string;
	domain?: readonly [number, number];
	spanSeconds: number;
	height: number;
	time?: ChartTime;
};

// Lines on a grid in plain SVG, 1 unit = 1 pixel so text stays crisp; newest at the left in RTL.
export function ChartPlot({
	title,
	times,
	series,
	format,
	axisFormat,
	domain,
	spanSeconds,
	height,
	time,
}: PlotProps) {
	const ref = useRef<HTMLDivElement>(null);
	const { width, rtl } = useElementBox(ref);
	const dom = niceDomain(
		series.flatMap((item) => [...item.values]),
		domain,
	);
	const labels = dom.ticks.map(axisFormat);
	const widest = Math.max(0, ...labels.map((label) => label.length));
	const axis = Math.min(100, Math.max(34, widest * 6.5 + 12));
	const frame: PlotFrame = {
		width,
		height,
		axis,
		rtl,
		top: TOP,
		bottom: height - BOTTOM,
		left: rtl ? EDGE : axis,
		right: width - (rtl ? axis : EDGE),
	};
	const first = times[0] ?? 0;
	const last = times[times.length - 1] ?? 0;
	const xs = makeXScale(first, last, frame.left, frame.right - frame.left, rtl);
	const y = (value: number) =>
		TOP + (1 - (value - dom.min) / (dom.max - dom.min)) * (frame.bottom - TOP);
	const scrub = useScrub({
		count: times.length,
		reversed: rtl,
		indexAt: (x) => nearestIndex(times, xs.time(x)),
	});
	const at = scrub.index;
	const current = at ?? times.length - 1;
	const hoverX = at === null ? 0 : xs.x(times[at] ?? 0);
	return (
		<div ref={ref} className="relative">
			<div className="rounded-lg focus-within:outline-2 focus-within:outline-offset-1 focus-within:outline-focus">
				<input
					type="range"
					className="sr-only"
					aria-label={`${t.chart.plotLabel(title)}. ${t.chart.plotHint}`}
					min={0}
					max={Math.max(0, times.length - 1)}
					value={at ?? times.length - 1}
					aria-valuetext={pointText(times[current] ?? 0, current, series, format, time)}
					onChange={(event) => scrub.select(Number(event.target.value))}
					onKeyDown={scrub.onKeyDown}
					onFocus={scrub.onFocus}
					onBlur={scrub.onBlur}
				/>
				<svg
					viewBox={`0 0 ${width} ${height}`}
					width="100%"
					height={height}
					aria-hidden
					onPointerMove={scrub.onPointerMove}
					onPointerLeave={scrub.onPointerLeave}
					className="block touch-pan-y select-none [direction:ltr]"
				>
					<ChartAxes
						frame={frame}
						domain={dom}
						labels={labels}
						y={y}
						xs={xs}
						range={[first, last]}
						spanSeconds={spanSeconds}
						time={time}
					/>
					<SeriesLines
						series={series}
						times={times}
						xs={xs}
						y={y}
						baseline={y(dom.min)}
						maxGap={gapLimit(times)}
					/>
					{at === null ? null : (
						<Crosshair x={hoverX} top={TOP} bottom={frame.bottom} at={at} series={series} y={y} />
					)}
				</svg>
			</div>
			{at === null ? null : (
				<ChartTooltip
					moment={times[at] ?? 0}
					time={time}
					index={at}
					series={series}
					format={format}
					x={hoverX}
					width={width}
				/>
			)}
		</div>
	);
}
