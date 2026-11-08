export type AccountTab = "account" | "notifications";

export const isAccountTab = (value: unknown): value is AccountTab =>
	value === "account" || value === "notifications";
