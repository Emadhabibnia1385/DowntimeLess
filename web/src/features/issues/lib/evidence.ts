import { formatDecimal, formatDuration, formatMs, formatPercent, t } from "@/strings";

const LABELS: Record<string, string> = t.issues.evidenceLabels;

export type EvidenceRow = { key: string; label: string; value: string; ltr: boolean };

function valueText(key: string, value: unknown): string {
	if (typeof value === "number") {
		if (key.endsWith("_pct")) return formatPercent(value);
		if (key.endsWith("_ms")) return formatMs(value);
		if (key.endsWith("_s_ago")) return formatDuration(value);
		return formatDecimal(value, 1);
	}
	if (Array.isArray(value)) return value.join(", ");
	return String(value ?? t.common.none);
}

/** An issue's evidence as labelled, formatted rows; names and addresses stay left to right. */
export function evidenceRows(evidence: Record<string, unknown>): EvidenceRow[] {
	return Object.entries(evidence).map(([key, value]) => ({
		key,
		label: LABELS[key] ?? key,
		value: valueText(key, value),
		ltr: typeof value !== "number",
	}));
}
