import { areaPath, linePath, splitSegments, type XScale } from "./lib";
import { type ChartSeries, TONE_TEXT } from "./types";

// Each series as one path per unbroken run; a lone point is a dot; an optional soft area under it.
export function SeriesLines({
	series,
	times,
	xs,
	y,
	baseline,
	maxGap,
}: {
	series: readonly ChartSeries[];
	times: readonly number[];
	xs: XScale;
	y: (value: number) => number;
	baseline: number;
	maxGap: number;
}) {
	return (
		<g>
			{series.map((item) =>
				splitSegments(times, item.values, maxGap).map((run) => {
					const points = run.map((i) => ({
						x: xs.x(times[i] ?? 0),
						y: y(item.values[i] ?? 0),
					}));
					const [only] = points;
					return (
						<g key={`${item.key}-${run[0]}`} className={TONE_TEXT[item.tone]}>
							{points.length === 1 && only ? (
								<circle cx={only.x} cy={only.y} r={2.5} fill="currentColor" />
							) : (
								<>
									{item.area ? (
										<path d={areaPath(points, baseline)} fill="currentColor" fillOpacity={0.12} />
									) : null}
									<path
										d={linePath(points)}
										fill="none"
										stroke="currentColor"
										strokeWidth={2}
										strokeLinejoin="round"
										strokeLinecap="round"
									/>
								</>
							)}
						</g>
					);
				}),
			)}
		</g>
	);
}
