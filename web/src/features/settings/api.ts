import { useSettingsGet } from "@/api/generated/settings/settings";
import { DEFAULT_SETTINGS } from "./lib/rules";

/** The alert settings, with the defaults filling anything the master did not send. */
export function useThresholds(): Record<string, number> {
	const settings = useSettingsGet();
	return { ...DEFAULT_SETTINGS, ...settings.data };
}
