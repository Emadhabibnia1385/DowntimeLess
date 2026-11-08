import { formatTick } from "@/strings";
import type { Domain, XScale } from "./lib";
import type { PlotFrame } from "./types";

const LABEL = "fill-current text-xs text-muted";

// A horizontal grid with value labels at the reading start (right in RTL) and time labels below.
export function ChartAxes({
	frame,
	domain,
	labels,
	y,
	xs,
	range,
	spanSeconds,
}: {
	frame: PlotFrame;
	domain: Domain;
	labels: readonly string[];
	y: (value: number) => number;
	xs: XScale;
	range: readonly [number, number];
	spanSeconds: number;
}) {
	const { left, right, width, height, axis, rtl } = frame;
	const count = Math.max(2, Math.min(7, Math.floor((right - left) / 80)));
	const [first, last] = range;
	const ticks = Array.from({ length: count }, (_, i) => first + ((last - first) * i) / (count - 1));
	return (
		<g>
			{domain.ticks.map((tick, i) => (
				<g key={tick}>
					<line
						x1={left}
						x2={right}
						y1={y(tick)}
						y2={y(tick)}
						className="stroke-border"
						strokeWidth={1}
					/>
					<text
						x={rtl ? width - 4 : axis - 6}
						y={y(tick)}
						textAnchor="end"
						dominantBaseline="middle"
						className={LABEL}
					>
						{labels[i]}
					</text>
				</g>
			))}
			{ticks.map((tick) => {
				const x = xs.x(tick);
				const anchor = x - 32 < left ? "start" : x + 32 > right ? "end" : "middle";
				return (
					<text key={tick} x={x} y={height - 6} textAnchor={anchor} className={LABEL}>
						{formatTick(tick, spanSeconds)}
					</text>
				);
			})}
		</g>
	);
}
