/** Metrics ranges the master serves, with their length in seconds. */
export const RANGES = {
	"1h": 3600,
	"6h": 21_600,
	"24h": 86_400,
	"7d": 604_800,
	"30d": 2_592_000,
} as const;
export type Range = keyof typeof RANGES;

/** The ranges the history card offers as chips. */
export const CHIP_RANGES: readonly Range[] = ["6h", "24h", "7d", "30d"];

export const isRange = (value: unknown): value is Range =>
	typeof value === "string" && value in RANGES;
