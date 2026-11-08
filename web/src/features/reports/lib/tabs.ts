export const REPORT_TABS = ["ai", "health", "changes", "playbooks"] as const;
export type ReportsTab = (typeof REPORT_TABS)[number];

export const isReportsTab = (value: unknown): value is ReportsTab =>
	typeof value === "string" && (REPORT_TABS as readonly string[]).includes(value);

export const DETAILS = ["brief", "full"] as const;
export type Detail = (typeof DETAILS)[number];

export const PERIODS = { "24h": 86_400, "7d": 7 * 86_400, "30d": 30 * 86_400 } as const;
export type Period = keyof typeof PERIODS;
