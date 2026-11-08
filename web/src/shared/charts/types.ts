// Written out, not built from the tone name: Tailwind only keeps class names it can read.
export const TONE_TEXT = {
	accent: "text-accent",
	info: "text-info",
	warning: "text-warning",
	success: "text-success",
	danger: "text-danger",
	muted: "text-muted",
} as const;

export type SeriesTone = keyof typeof TONE_TEXT;

export type ChartSeries = {
	key: string;
	label: string;
	tone: SeriesTone;
	/** One value per time; null is a gap and breaks the line. */
	values: readonly (number | null)[];
	/** A soft fill under the line. */
	area?: boolean;
	/** Overrides the chart's value format for this series. */
	format?: (value: number) => string;
};

/** The plot's box in pixels, the y axis' width and the reading direction. */
export type PlotFrame = {
	width: number;
	height: number;
	left: number;
	right: number;
	top: number;
	bottom: number;
	axis: number;
	rtl: boolean;
};
