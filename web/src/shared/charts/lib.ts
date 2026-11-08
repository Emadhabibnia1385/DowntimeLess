export type Domain = { min: number; max: number; ticks: number[] };

const STEPS = [1, 2, 2.5, 5, 10];

/** A round step (1, 2, 2.5, 5 times a power of ten) that gives about `count` intervals. */
export function niceStep(span: number, count: number): number {
	if (!(span > 0)) return 1;
	const raw = span / Math.max(1, count);
	const base = 10 ** Math.floor(Math.log10(raw));
	return (STEPS.find((step) => step >= raw / base - 1e-9) ?? 10) * base;
}

function ticksBetween(min: number, max: number, step: number): number[] {
	const ticks: number[] = [];
	for (let i = Math.ceil(min / step - 1e-9); i * step <= max + step * 1e-9; i += 1) {
		ticks.push(Number((i * step).toPrecision(12)));
	}
	return ticks;
}

/** The y range and its ticks: the fixed one as given, else 0 (or below) up to a round top. */
export function niceDomain(
	values: readonly (number | null)[],
	fixed?: readonly [number, number],
	count = 4,
): Domain {
	if (fixed) {
		const [min, max] = fixed;
		return { min, max, ticks: ticksBetween(min, max, niceStep(max - min, count)) };
	}
	const present = values.filter((value): value is number => value !== null);
	const low = Math.min(0, ...present);
	const high = Math.max(0, ...present);
	const step = niceStep(high > low ? high - low : 1, count);
	const min = Math.floor(low / step) * step;
	const max = high > low ? Math.ceil(high / step) * step : min + 1;
	return { min, max, ticks: ticksBetween(min, max, step) };
}

export type XScale = { x: (time: number) => number; time: (x: number) => number };

/** Time to pixels over [left, left + width]; `reversed` puts the newest at the left. */
export function makeXScale(
	min: number,
	max: number,
	left: number,
	width: number,
	reversed: boolean,
): XScale {
	const span = max - min || 1;
	return {
		x: (time) => {
			const ratio = max === min ? 0.5 : (time - min) / span;
			return left + (reversed ? 1 - ratio : ratio) * width;
		},
		time: (x) => {
			const ratio = Math.min(1, Math.max(0, (x - left) / width));
			return min + (reversed ? 1 - ratio : ratio) * span;
		},
	};
}

/** The index of the time closest to `target` in an ascending list; -1 when empty. */
export function nearestIndex(times: readonly number[], target: number): number {
	if (times.length === 0) return -1;
	let low = 0;
	let high = times.length - 1;
	while (low < high) {
		const mid = (low + high) >> 1;
		if ((times[mid] ?? 0) < target) low = mid + 1;
		else high = mid;
	}
	const before = Math.max(0, low - 1);
	return Math.abs((times[before] ?? 0) - target) <= Math.abs((times[low] ?? 0) - target)
		? before
		: low;
}

/** A jump longer than this between two samples is a hole, not a slope: 3.5 times the usual step. */
export function gapLimit(times: readonly number[]): number {
	const steps = times
		.slice(1)
		.map((time, index) => time - (times[index] ?? 0))
		.filter((step) => step > 0)
		.sort((a, b) => a - b);
	const median = steps[Math.floor(steps.length / 2)];
	return steps.length < 3 || median === undefined ? Number.POSITIVE_INFINITY : median * 3.5;
}

/** Runs of indexes to draw as one line each: null values and long holes in time split them. */
export function splitSegments(
	times: readonly number[],
	values: readonly (number | null)[],
	maxGap = Number.POSITIVE_INFINITY,
): number[][] {
	const runs: number[][] = [];
	let run: number[] = [];
	values.forEach((value, index) => {
		if (value === null || value === undefined) {
			if (run.length) runs.push(run);
			run = [];
			return;
		}
		const last = run[run.length - 1];
		if (last !== undefined && (times[index] ?? 0) - (times[last] ?? 0) > maxGap) {
			runs.push(run);
			run = [];
		}
		run.push(index);
	});
	if (run.length) runs.push(run);
	return runs;
}

const fixed = (value: number) => value.toFixed(1);

export type Point = { x: number; y: number };

/** An SVG path through the points: "M x y L x y ...". */
export const linePath = (points: readonly Point[]): string =>
	points.map((p, index) => `${index === 0 ? "M" : "L"}${fixed(p.x)} ${fixed(p.y)}`).join("");

/** The same line closed down to `baseline`, for a soft fill. */
export function areaPath(points: readonly Point[], baseline: number): string {
	const first = points[0];
	const last = points[points.length - 1];
	if (!first || !last) return "";
	return `${linePath(points)}L${fixed(last.x)} ${fixed(baseline)}L${fixed(first.x)} ${fixed(baseline)}Z`;
}

export type CsvCell = string | number | null;

const quote = (cell: string) => (/[",\r\n]/.test(cell) ? `"${cell.replaceAll('"', '""')}"` : cell);

/** A number as Excel reads it: Latin digits, a dot, no grouping, at most 3 decimals. */
export const csvNumber = (value: number): string => String(Number(value.toFixed(3)));

/** CSV text with CRLF rows; empty cells for gaps. */
export function toCsv(header: readonly string[], rows: readonly (readonly CsvCell[])[]): string {
	const text = (cell: CsvCell) =>
		cell === null ? "" : typeof cell === "number" ? csvNumber(cell) : quote(cell);
	return [header, ...rows].map((row) => row.map(text).join(",")).join("\r\n");
}

/** "2026-11-08 14:30:00" in the viewer's zone (or `offsetMinutes` behind UTC): Excel reads it. */
export function csvTime(
	epochSeconds: number,
	offsetMinutes = new Date(epochSeconds * 1000).getTimezoneOffset(),
): string {
	return new Date((epochSeconds - offsetMinutes * 60) * 1000)
		.toISOString()
		.slice(0, 19)
		.replace("T", " ");
}

/** UTF-8 with a byte order mark, so Excel does not guess a legacy code page. */
export const csvBlob = (text: string): Blob =>
	new Blob(["﻿", text], { type: "text/csv;charset=utf-8" });
