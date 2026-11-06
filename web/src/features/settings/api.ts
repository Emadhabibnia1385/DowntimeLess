import { useSettingsGet } from "@/api/generated/settings/settings";

// The master's defaults, used until the real thresholds arrive.
export const DEFAULT_THRESHOLDS: Record<string, number> = {
	cpu_warn: 90,
	steal_warn: 10,
	ram_warn: 90,
	disk_warn: 85,
	disk_crit: 95,
	retrans_warn: 5,
	conntrack_crit: 85,
	loss_warn: 10,
	loss_crit: 50,
};

/** The alert thresholds, with the defaults filling anything the master did not send. */
export function useThresholds(): Record<string, number> {
	const settings = useSettingsGet();
	return { ...DEFAULT_THRESHOLDS, ...settings.data };
}
