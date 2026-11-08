export type IssuesTab = "now" | "history";

export const isIssuesTab = (value: unknown): value is IssuesTab =>
	value === "now" || value === "history";

export const HISTORY_RANGES = ["24h", "7d", "30d"] as const;
export type HistoryRange = (typeof HISTORY_RANGES)[number];

export const isHistoryRange = (value: unknown): value is HistoryRange =>
	typeof value === "string" && (HISTORY_RANGES as readonly string[]).includes(value);
