import { type ChartSeries, TONE_TEXT } from "./types";

// A dashed line at the chosen time with a dot on every shown series.
export function Crosshair({
	x,
	top,
	bottom,
	at,
	series,
	y,
}: {
	x: number;
	top: number;
	bottom: number;
	at: number;
	series: readonly ChartSeries[];
	y: (value: number) => number;
}) {
	return (
		<g>
			<line
				x1={x}
				x2={x}
				y1={top}
				y2={bottom}
				className="stroke-muted"
				strokeWidth={1}
				strokeDasharray="3 3"
			/>
			{series.map((item) => {
				const value = item.values[at];
				return value == null ? null : (
					<circle
						key={item.key}
						cx={x}
						cy={y(value)}
						r={4}
						strokeWidth={2}
						fill="currentColor"
						className={`${TONE_TEXT[item.tone]} stroke-surface`}
					/>
				);
			})}
		</g>
	);
}
