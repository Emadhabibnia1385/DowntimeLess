import { EVENT_KINDS } from "./events";
import { type Band, BANDS } from "./health";

export type IssuesTab = "now" | "history" | "health" | "changes" | "guides";

export const ISSUES_TABS: readonly IssuesTab[] = ["now", "history", "health", "changes", "guides"];

export const isIssuesTab = (value: unknown): value is IssuesTab =>
	typeof value === "string" && (ISSUES_TABS as readonly string[]).includes(value);

export const HISTORY_RANGES = ["24h", "7d", "30d"] as const;
export type HistoryRange = (typeof HISTORY_RANGES)[number];

export const isHistoryRange = (value: unknown): value is HistoryRange =>
	typeof value === "string" && (HISTORY_RANGES as readonly string[]).includes(value);

export const PERIODS = { "24h": 86_400, "7d": 7 * 86_400, "30d": 30 * 86_400 } as const;
export type Period = keyof typeof PERIODS;

export const isPeriod = (value: unknown): value is Period =>
	typeof value === "string" && value in PERIODS;

export const isEventKind = (value: unknown): value is string =>
	typeof value === "string" && (EVENT_KINDS as readonly string[]).includes(value);

export const isBand = (value: unknown): value is Band =>
	typeof value === "string" && (BANDS as readonly string[]).includes(value);

/** The filters of the health and changes tabs; "all" means no filter. */
export type IssuesFilters = { period: Period; kind: string; band: Band | "all" };

export const DEFAULT_FILTERS: IssuesFilters = { period: "24h", kind: "all", band: "all" };

/** The filters as address parameters; a value equal to its default stays out of the address. */
export function filtersToSearch(filters: IssuesFilters): {
	period?: Period;
	kind?: string;
	band?: Band;
} {
	return {
		period: filters.period === DEFAULT_FILTERS.period ? undefined : filters.period,
		kind: filters.kind === DEFAULT_FILTERS.kind ? undefined : filters.kind,
		band: filters.band === "all" ? undefined : filters.band,
	};
}
