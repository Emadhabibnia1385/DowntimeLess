import { CHIP_RANGES, type Range } from "@/features/servers";

/** The ranges the dashboard offers: the chips of the server page. */
export const isDashRange = (value: unknown): value is Range =>
	typeof value === "string" && (CHIP_RANGES as readonly string[]).includes(value);

export const DEFAULT_RANGE: Range = "24h";
