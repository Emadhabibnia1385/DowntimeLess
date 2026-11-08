import type { EventOut } from "@/api/generated/model";
import { formatNumber, t } from "@/strings";

export const EVENT_KINDS = Object.keys(
	t.issueChanges.kinds,
) as (keyof typeof t.issueChanges.kinds)[];

const W = t.issueChanges.what;
const NEEDS_DETAIL = new Set([
	"agent_updated",
	"job_created",
	"job_done",
	"ip_changed",
	"server_renamed",
	"settings_changed",
]);
const text = (value: unknown): string => (typeof value === "string" ? value : String(value ?? ""));

export function kindLabel(kind: string): string {
	return (t.issueChanges.kinds as Record<string, string>)[kind] ?? kind;
}

export function kindTone(kind: string): "danger" | "warning" | "success" | "info" | "neutral" {
	if (kind === "rebooted" || kind === "ip_changed" || kind === "resized" || kind === "issue_opened")
		return "warning";
	if (kind === "server_removed") return "danger";
	if (kind === "issue_closed" || kind === "server_added") return "success";
	if (kind === "job_created" || kind === "job_done" || kind === "agent_updated") return "info";
	return "neutral";
}

/** The event in words, built from its structured detail; the master's title is the fallback. */
export function describeEvent(event: EventOut): string {
	const d = event.detail as Record<string, unknown>;
	if (Object.keys(d).length === 0 && NEEDS_DETAIL.has(event.kind)) return event.title;
	switch (event.kind) {
		case "job_created":
			return W.job_created(text(d.job_kind));
		case "job_done": {
			const status = text(d.status);
			const label = (t.issueChanges.jobStatus as Record<string, string>)[status] ?? status;
			return W.job_done(text(d.job_kind), label);
		}
		case "agent_updated":
			return W.agent_updated(text(d.old), text(d.new));
		case "server_added":
			return W.server_added((t.roles as Record<string, string>)[text(d.role)] ?? text(d.role));
		case "server_removed":
			return W.server_removed(event.title);
		case "server_renamed":
			return W.server_renamed(
				d.field === "alias" ? W.aliasField : W.nameField,
				text(d.old) || t.common.none,
				text(d.new) || t.common.none,
			);
		case "acct_toggled":
			return d.acct_on ? W.acct_on : W.acct_off;
		case "issue_opened":
			return W.issue_opened(text(d.code));
		case "issue_closed":
			return W.issue_closed(text(d.code));
		case "issue_acked":
			return W.issue_acked(
				text(d.code),
				(t.issueAcks.modes as Record<string, string>)[text(d.mode)] ?? text(d.mode),
			);
		case "issue_unacked":
			return W.issue_unacked(text(d.key));
		case "rebooted":
			return W.rebooted;
		case "resized":
			return W.resized;
		case "ip_changed":
			return W.ip_changed(text(d.old), text(d.new));
		case "settings_changed":
			return W.settings_changed(
				Array.isArray(d.keys) ? d.keys.map(String).join("، ") : formatNumber(0),
			);
		case "check_ack":
			return W.check_ack(
				(W.checkWhat as Record<string, string>)[text(d.what)] ?? text(d.what),
				text(d.name),
				d.ignored !== false,
			);
		default:
			return event.title;
	}
}
