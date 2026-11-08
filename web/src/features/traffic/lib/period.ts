// Reporting periods in whole Tehran days (UTC+03:30, no daylight saving since 2022).
export const TEHRAN_OFFSET_MIN = 210;
const OFFSET_S = TEHRAN_OFFSET_MIN * 60;
const DAY = 86_400;
export const MAX_DAYS = 366;

export const PERIOD_IDS = [
	"today",
	"yesterday",
	"7d",
	"30d",
	"90d",
	"month",
	"prev-month",
	"jmonth",
	"prev-jmonth",
	"custom",
] as const;

export type PeriodId = (typeof PERIOD_IDS)[number];

export const isPeriodId = (value: unknown): value is PeriodId =>
	typeof value === "string" && (PERIOD_IDS as readonly string[]).includes(value);

/** The chosen period as the address keeps it: a preset, or a custom range of calendar days. */
export type Period = { id: PeriodId; from?: string; to?: string };

export const DEFAULT_PERIOD: Period = { id: "30d" };

const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Days since 1970-01-01 of a "YYYY-MM-DD" text, or null when it is not a real date. */
export function parseDay(text: string | undefined): number | null {
	const match = text ? ISO_DAY.exec(text) : null;
	if (!match) return null;
	const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
	const ms = Date.UTC(year, month - 1, day);
	const check = new Date(ms);
	if (check.getUTCMonth() !== month - 1 || check.getUTCDate() !== day) return null;
	return ms / 86_400_000;
}

/** "YYYY-MM-DD" of a day count. */
export function dayText(dayIndex: number): string {
	return new Date(dayIndex * 86_400_000).toISOString().slice(0, 10);
}

/** The Tehran day (days since 1970-01-01) that contains a moment in epoch seconds. */
export const tehranDay = (epochSeconds: number): number =>
	Math.floor((epochSeconds + OFFSET_S) / DAY);

/** Epoch seconds of Tehran midnight at the start of a day count. */
export const dayStart = (dayIndex: number): number => dayIndex * DAY - OFFSET_S;

const PERSIAN = new Intl.DateTimeFormat("en-u-ca-persian-nu-latn", {
	timeZone: "UTC",
	year: "numeric",
	month: "numeric",
	day: "numeric",
});

/** Jalali year, month (1 to 12) and day of a day count. */
export function jalaliOf(dayIndex: number): { year: number; month: number; day: number } {
	const parts = PERSIAN.formatToParts(new Date(dayIndex * 86_400_000));
	const get = (type: string) => Number(parts.find((part) => part.type === type)?.value);
	return { year: get("year"), month: get("month"), day: get("day") };
}

/** [first day, day after the last] of the Jalali month of a day, `back` months earlier. */
export function jalaliMonth(dayIndex: number, back = 0): [number, number] {
	const startOf = (day: number) => day - (jalaliOf(day).day - 1);
	let start = startOf(dayIndex);
	for (let i = 0; i < back; i += 1) start = startOf(start - 1);
	// 31 days later is always inside the next month (months last 29 to 31 days)
	return [start, startOf(start + 31)];
}

/** [first day, day after the last] of the Gregorian month of a day, `back` months earlier. */
export function gregorianMonth(dayIndex: number, back = 0): [number, number] {
	const date = new Date(dayIndex * 86_400_000);
	const first = Date.UTC(date.getUTCFullYear(), date.getUTCMonth() - back, 1) / 86_400_000;
	const next = new Date(first * 86_400_000);
	return [first, Date.UTC(next.getUTCFullYear(), next.getUTCMonth() + 1, 1) / 86_400_000];
}

export type Window = { since: number; until: number };

/** The days [first, last + 1) a period covers, or null for a custom range that is not valid. */
export function periodDays(period: Period, nowSeconds: number): [number, number] | null {
	const today = tehranDay(nowSeconds);
	switch (period.id) {
		case "today":
			return [today, today + 1];
		case "yesterday":
			return [today - 1, today];
		case "7d":
			return [today - 6, today + 1];
		case "30d":
			return [today - 29, today + 1];
		case "90d":
			return [today - 89, today + 1];
		case "month":
			return gregorianMonth(today);
		case "prev-month":
			return gregorianMonth(today, 1);
		case "jmonth":
			return jalaliMonth(today);
		case "prev-jmonth":
			return jalaliMonth(today, 1);
		case "custom": {
			const from = parseDay(period.from);
			const to = parseDay(period.to);
			if (from === null || to === null || to < from || to - from + 1 > MAX_DAYS) return null;
			return [from, to + 1];
		}
	}
}

/** The window to ask the API for, in epoch seconds; null when the period is not valid. */
export function periodWindow(period: Period, nowSeconds: number): Window | null {
	const days = periodDays(period, nowSeconds);
	return days ? { since: dayStart(days[0]), until: dayStart(days[1]) } : null;
}

/** How many Tehran days the window spans. */
export const windowDays = (window: Window): number =>
	Math.round((window.until - window.since) / DAY);

/** A custom range for the fields to start from: the last 7 days. */
export function defaultCustom(nowSeconds: number): Period {
	const today = tehranDay(nowSeconds);
	return { id: "custom", from: dayText(today - 6), to: dayText(today) };
}
