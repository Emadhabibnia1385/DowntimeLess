export type Sample = { ts: number; value: number | null };

export type Bar = { ts: number; value: number | null };

/** Metrics ranges the master serves, with their length in seconds. */
export const RANGES = { "1h": 3600, "24h": 86_400, "7d": 604_800, "30d": 2_592_000 } as const;
export type Range = keyof typeof RANGES;

export const isRange = (value: unknown): value is Range =>
	typeof value === "string" && value in RANGES;

/** Merges consecutive samples into at most `maxBars` bars: a mean for levels, a sum for traffic. */
export function bucketSamples(
	samples: readonly Sample[],
	mode: "mean" | "sum",
	maxBars = 60,
): Bar[] {
	const size = Math.max(1, Math.ceil(samples.length / maxBars));
	const bars: Bar[] = [];
	for (let start = 0; start < samples.length; start += size) {
		const group = samples.slice(start, start + size);
		const values = group.flatMap((sample) => (sample.value === null ? [] : [sample.value]));
		const total = values.reduce((sum, value) => sum + value, 0);
		const value = values.length === 0 ? null : mode === "sum" ? total : total / values.length;
		bars.push({ ts: group[0]?.ts ?? 0, value });
	}
	return bars;
}

/** The biggest value among the bars, or 0 when none has data. */
export function peakOf(bars: readonly Bar[]): number {
	return Math.max(0, ...bars.map((bar) => bar.value ?? 0));
}
