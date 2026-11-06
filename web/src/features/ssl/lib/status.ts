import type { SslRow } from "@/api/generated/model";
import { formatNumber, t } from "@/strings";

export type CertTone = "success" | "warning" | "danger" | "neutral";

export type CertStatus = { tone: CertTone; label: string };

const LEVEL_TONES: Record<string, CertTone> = {
	ok: "success",
	warning: "warning",
	critical: "danger",
};

/** The days left in words: "منقضی شده", "امروز منقضی می‌شود" or "۳ روز مانده". */
export function daysLeftLabel(days: number): string {
	if (days < 0) return t.ssl.expired;
	if (days === 0) return t.ssl.today;
	return t.ssl.daysLeft(formatNumber(days));
}

/** A certificate's state as a tone and a word, so the chip never relies on colour alone. */
export function certStatus(
	row: Pick<SslRow, "level" | "days_left" | "error" | "checked_at">,
): CertStatus {
	if (row.error) return { tone: "danger", label: t.ssl.checkFailed };
	if (row.days_left === null) {
		return {
			tone: "neutral",
			label: row.checked_at === null ? t.ssl.notChecked : t.common.unknown,
		};
	}
	if (row.days_left < 0) return { tone: "danger", label: t.ssl.expired };
	if (row.level === "ok") return { tone: "success", label: t.ssl.healthy };
	return { tone: LEVEL_TONES[row.level] ?? "neutral", label: daysLeftLabel(row.days_left) };
}

const RENEW: Record<string, CertStatus> = {
	on: { tone: "success", label: t.ssl.renewOn },
	off: { tone: "warning", label: t.ssl.renewOff },
};

/** Whether the certificate renews itself; a domain checked from outside cannot tell. */
export const autoRenewStatus = (value: string): CertStatus =>
	RENEW[value] ?? { tone: "neutral", label: t.ssl.renewUnknown };

export type SslSummary = {
	total: number;
	expiring: number;
	critical: number;
	autoRenewOff: number;
};

/** The counts the summary cards and the dashboard show. */
export function summarize(rows: readonly Pick<SslRow, "level" | "auto_renew">[]): SslSummary {
	return {
		total: rows.length,
		expiring: rows.filter((row) => row.level === "warning").length,
		critical: rows.filter((row) => row.level === "critical").length,
		autoRenewOff: rows.filter((row) => row.auto_renew === "off").length,
	};
}
