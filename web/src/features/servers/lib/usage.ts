import type { Latest } from "@/api/generated/model";
import { formatDecimal, formatPercent, t } from "@/strings";

export type Usage = { percent: string; detail: string | null };

const MB_PER_GB = 1024;

export function cpuUsage(latest: Latest): Usage | null {
	if (latest.cpu_pct == null) return null;
	return { percent: formatPercent(latest.cpu_pct), detail: null };
}

export function ramUsage(latest: Latest): Usage | null {
	if (latest.ram_pct == null) return null;
	const { ram_used_mb: used, ram_total_mb: total } = latest;
	return {
		percent: formatPercent(latest.ram_pct),
		detail:
			used != null && total
				? t.servers.gigUsed(formatDecimal(used / MB_PER_GB), formatDecimal(total / MB_PER_GB))
				: null,
	};
}

export function diskUsage(latest: Latest): Usage | null {
	if (latest.disk_pct == null) return null;
	const { disk_used_gb: used, disk_total_gb: total } = latest;
	return {
		percent: formatPercent(latest.disk_pct),
		detail:
			used != null && total ? t.servers.gigUsed(formatDecimal(used), formatDecimal(total)) : null,
	};
}
