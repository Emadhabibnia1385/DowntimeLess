import { formatDateTime, t } from "@/strings";
import { type ChartSeries, TONE_TEXT } from "./types";

// The values of every shown series at one time, beside the crosshair; spoken politely too.
export function ChartTooltip({
	time,
	index,
	series,
	format,
	x,
	width,
}: {
	time: number;
	index: number;
	series: readonly ChartSeries[];
	format: (value: number) => string;
	x: number;
	width: number;
}) {
	const flip = x > width / 2;
	return (
		<output
			className="pointer-events-none absolute block top-2 z-10 min-w-36 rounded-xl border border-border bg-overlay px-3 py-2 text-xs text-overlay-foreground shadow-overlay"
			style={{
				left: x,
				transform: `translateX(${flip ? "calc(-100% - 12px)" : "12px"})`,
			}}
		>
			<p className="mb-1 font-semibold">{formatDateTime(time)}</p>
			<ul className="flex flex-col gap-1">
				{series.map((item) => {
					const value = item.values[index];
					return (
						<li key={item.key} className="flex items-center justify-between gap-4">
							<span className="flex items-center gap-1.5">
								<span
									aria-hidden
									className={`size-2 rounded-full bg-current ${TONE_TEXT[item.tone]}`}
								/>
								{item.label}
							</span>
							<span className="font-semibold tabular-nums">
								{value == null ? t.common.none : (item.format ?? format)(value)}
							</span>
						</li>
					);
				})}
			</ul>
		</output>
	);
}
