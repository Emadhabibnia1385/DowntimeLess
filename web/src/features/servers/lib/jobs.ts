import type { JobOut } from "@/api/generated/model";
import { formatBitRate, formatMs, formatNumber, formatPercent, t } from "@/strings";

// Public endpoints the agent downloads from and uploads to when asked to measure its speed.
export const SPEEDTEST_DOWN_URL = "https://speed.cloudflare.com/__down?bytes=25000000";
export const SPEEDTEST_UP_URL = "https://speed.cloudflare.com/__up";

/** Jobs that change the server and so need a human to confirm. */
export const MUTATING_KINDS = ["apt_upgrade_safe", "reboot", "self_update"] as const;

const num = (value: unknown): number | null => (typeof value === "number" ? value : null);

/** The text a diagnostic job returned, if it has any. */
export function jobOutput(job: Pick<JobOut, "result">): string | null {
	const output = job.result?.output;
	return typeof output === "string" && output !== "" ? output : null;
}

/** A job's outcome in one short line of Persian; empty while it has not finished. */
export function jobResultText(job: Pick<JobOut, "kind" | "status" | "result" | "error">): string {
	if (job.status === "error" || job.status === "rejected") {
		if (job.error === "permission level does not allow this job")
			return t.server.jobErrorPermission;
		return job.error ?? t.common.none;
	}
	const result = job.result ?? {};
	if (job.kind === "ping") {
		const loss = num(result.loss_pct);
		const rtt = num(result.rtt_ms);
		if (loss === null) return t.common.none;
		return rtt === null ? formatPercent(loss) : `${formatPercent(loss)} · ${formatMs(rtt)}`;
	}
	if (job.kind === "speedtest_down" || job.kind === "speedtest_up") {
		const mbps = num(result.mbps);
		return mbps === null ? t.common.none : formatBitRate(mbps * 1_000_000);
	}
	if (job.kind === "http_check") {
		const status = num(result.status);
		return status === null ? t.common.none : t.server.outputHttp(formatNumber(status));
	}
	if (job.kind === "tcp_check") {
		return result.open === true ? t.server.jobOpen : t.server.jobClosed;
	}
	return t.common.none;
}
