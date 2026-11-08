import { fa } from "./fa";

// Persian digits, grouping and the Jalali calendar come from Intl, never from our own maths.
const LOCALE = "fa-IR-u-ca-persian";

const numbers = new Intl.NumberFormat("fa-IR");
const percent = new Intl.NumberFormat("fa-IR", { style: "percent", maximumFractionDigits: 1 });

/** A whole or fractional number with Persian digits and grouping: "۱٬۲۳۴". */
export function formatNumber(value: number): string {
	return numbers.format(value);
}

/** A number with at most `digits` decimals: "۰٫۵", "۱۲٫۳". */
export function formatDecimal(value: number, digits = 1): string {
	return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: digits }).format(value);
}

/** A value already in percent (0 to 100) as "۱۲٫۵٪". */
export function formatPercent(pct: number): string {
	return percent.format(pct / 100);
}

/** A scaled size: the largest unit that keeps the number under `base`. */
function scaled(value: number, base: number, units: readonly string[]): string {
	let rest = Math.max(0, value);
	let step = 0;
	while (rest >= base && step < units.length - 1) {
		rest /= base;
		step += 1;
	}
	const digits = step === 0 ? 0 : rest >= 100 ? 0 : rest >= 10 ? 1 : 2;
	return `${formatDecimal(rest, digits)} ${units[step]}`;
}

const BYTE_UNITS = [
	fa.units.byte,
	fa.units.kilobyte,
	fa.units.megabyte,
	fa.units.gigabyte,
	fa.units.terabyte,
];

const BIT_UNITS = [fa.units.bit, fa.units.kilobit, fa.units.megabit, fa.units.gigabit];

/** A size in bytes ("۹۷۱ مگابایت", "۱٫۵ گیگابایت"); 1024 per step like the OS. */
export function formatBytes(bytes: number): string {
	return scaled(bytes, 1024, BYTE_UNITS);
}

/** A rate in bits per second; network links count in 1000s. */
export function formatBitRate(bitsPerSecond: number): string {
	return scaled(bitsPerSecond, 1000, BIT_UNITS);
}

/** A round-trip time: "۴۱٫۲ میلی‌ثانیه". */
export function formatMs(ms: number): string {
	return `${formatDecimal(ms, 1)} ${fa.units.millisecond}`;
}

/** A length of time in the two largest units: "۳ روز و ۴ ساعت", "۱۲ دقیقه". */
export function formatDuration(totalSeconds: number): string {
	const seconds = Math.max(0, Math.round(totalSeconds));
	const parts: [number, string][] = [
		[Math.floor(seconds / 86_400), fa.units.day],
		[Math.floor((seconds % 86_400) / 3600), fa.units.hour],
		[Math.floor((seconds % 3600) / 60), fa.units.minute],
	];
	const used = parts.filter(([amount]) => amount > 0).slice(0, 2);
	if (used.length === 0) return `${formatNumber(seconds)} ${fa.units.second}`;
	return used.map(([amount, unit]) => `${formatNumber(amount)} ${unit}`).join(` ${fa.units.and} `);
}

/** A moment (epoch seconds) as a Jalali date: "۱۴ مهر ۱۴۰۵". */
export function formatDate(epochSeconds: number, timeZone?: string): string {
	return new Intl.DateTimeFormat(LOCALE, { dateStyle: "medium", timeZone }).format(
		new Date(epochSeconds * 1000),
	);
}

/** The same with the time: "۱۴ مهر ۱۴۰۵، ۱۵:۳۰". */
export function formatDateTime(epochSeconds: number, timeZone?: string): string {
	return new Intl.DateTimeFormat(LOCALE, {
		dateStyle: "medium",
		timeStyle: "short",
		timeZone,
	}).format(new Date(epochSeconds * 1000));
}

/** Weekday, time with seconds, Gregorian and Jalali dates, in the device's zone unless given. */
export function formatClock(date: Date, timeZone?: string) {
	const day = { year: "numeric", month: "2-digit", day: "2-digit", timeZone } as const;
	return {
		weekday: new Intl.DateTimeFormat("fa-IR", { weekday: "long", timeZone }).format(date),
		time: new Intl.DateTimeFormat("fa-IR", {
			hour: "2-digit",
			minute: "2-digit",
			second: "2-digit",
			hourCycle: "h23",
			timeZone,
		}).format(date),
		gregorian: new Intl.DateTimeFormat("fa-IR-u-ca-gregory", day).format(date),
		jalali: new Intl.DateTimeFormat("fa-IR-u-ca-persian", day).format(date),
	};
}

/** A chart tick: the clock time for short ranges, the Jalali day for long ones. */
export function formatTick(epochSeconds: number, spanSeconds: number, timeZone?: string): string {
	const options: Intl.DateTimeFormatOptions =
		spanSeconds <= 86_400
			? { hour: "2-digit", minute: "2-digit", timeZone }
			: { day: "numeric", month: "short", timeZone };
	return new Intl.DateTimeFormat(LOCALE, options).format(new Date(epochSeconds * 1000));
}

const relative = new Intl.RelativeTimeFormat("fa-IR", { numeric: "auto" });

const UNITS: [limit: number, seconds: number, unit: Intl.RelativeTimeFormatUnit][] = [
	[60, 1, "second"],
	[3600, 60, "minute"],
	[86_400, 3600, "hour"],
	[2_592_000, 86_400, "day"],
	[31_536_000, 2_592_000, "month"],
];

/** "۲ ساعت پیش", "دیروز": a past time (epoch seconds) in Persian, relative to `now`. */
export function formatRelativeTime(epochSeconds: number, now = Date.now()): string {
	const diff = epochSeconds - now / 1000;
	const abs = Math.abs(diff);
	for (const [limit, seconds, unit] of UNITS) {
		if (abs < limit) return relative.format(Math.round(diff / seconds), unit);
	}
	return relative.format(Math.round(diff / 31_536_000), "year");
}
