import { formatDate, formatDateTime } from "@/strings";
import type { ChartTime } from "./types";

/** A chart moment as text: the date alone for daily points, else date and clock. */
export function timeText(epochSeconds: number, time?: ChartTime): string {
	return time?.dateOnly
		? formatDate(epochSeconds, time.timeZone)
		: formatDateTime(epochSeconds, time?.timeZone);
}
