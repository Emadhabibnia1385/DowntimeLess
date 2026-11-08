import type { Latest } from "@/api/generated/model";
import { formatDecimal, formatPercent, t } from "@/strings";

export type Usage = { percent: string; detail: string | null };

const MB_PER_GB = 1024;

/** "۷۵٪" and, when the agent reports the totals, "۳ از ۴ هسته درگیر". */
export function cpuUsage(latest: Latest): Usage | null {
	if (latest.cpu_pct == null) return null;
	const { cpu_cores: cores } = latest;
	const busy = cores ? Math.round(((latest.cpu_pct * cores) / 100) * 10) / 10 : null;
	return {
		percent: formatPercent(latest.cpu_pct),
		detail:
			cores && busy != null
				? t.servers.coresUsed(formatDecimal(busy), formatDecimal(cores, 0))
				: null,
	};
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
