import { z } from "zod";
import type { Issue } from "@/api/generated/model";
import { AckInMode } from "@/api/generated/model";
import { formatDateTime, t } from "@/strings";

export const ACK_MODES = Object.values(AckInMode);
export type AckMode = (typeof ACK_MODES)[number];

export const MODE_OPTIONS = ACK_MODES.map((mode) => ({
	value: mode,
	label: t.issueAcks.modes[mode],
	description: t.issueAcks.modeHints[mode],
}));

export const NOTE_MAX = 200;

export const ackSchema = z.object({
	mode: z.enum(AckInMode),
	note: z.string().trim().max(NOTE_MAX, { error: t.issueAcks.noteLong }),
});
export type AckValues = z.input<typeof ackSchema>;

/** The issues that still count and alert, and the ones the team acknowledged. */
export function splitAcked(issues: readonly Issue[]): { open: Issue[]; acked: Issue[] } {
	return {
		open: issues.filter((issue) => !issue.acked),
		acked: issues.filter((issue) => issue.acked),
	};
}

/** Until when an ack holds: a moment, or the mode in words when it has no end time. */
export function untilText(issue: Issue): string {
	if (issue.acked_until != null) return formatDateTime(issue.acked_until);
	const mode = issue.ack_mode as AckMode | null | undefined;
	return mode && mode in t.issueAcks.modes ? t.issueAcks.modes[mode] : t.common.none;
}
