import type { Issue } from "@/api/generated/model";
import { t } from "@/strings";

export type FixKind = "nft_reload" | "sysctl_apply" | "ipset_sync" | "tunnel_restart";
export type Fix = { kind: FixKind; args: Record<string, string> };

// Which alert offers which fix; any other alert offers none.
const BY_FAMILY: Record<string, Exclude<FixKind, "tunnel_restart">> = {
	dnat_missing: "nft_reload",
	dnat_dead_target: "nft_reload",
	drift_dnat: "nft_reload",
	drift_sysctl: "sysctl_apply",
	drift_ipset: "ipset_sync",
};
const UNIT =
	/^(backpack-|backhaul|gre-|wattun@|rathole|frps@|frpc@|gost)[A-Za-z0-9@._-]{0,80}\.service$/;

/** The one-click fix an issue offers, if any (a tunnel restart needs the unit the agent named). */
export function fixOf(issue: Pick<Issue, "code" | "evidence" | "server_id">): Fix | null {
	if (issue.server_id == null) return null;
	const family = issue.code.split(":")[0];
	const kind = BY_FAMILY[family];
	if (kind) return { kind, args: {} };
	const unit = (issue.evidence as Record<string, unknown>).unit;
	if (family === "tunnel_unhealthy" && typeof unit === "string" && UNIT.test(unit))
		return { kind: "tunnel_restart", args: { unit } };
	return null;
}

/** The exact commands the agent runs for a fix, as shown in the confirm dialog. */
export function fixCommand(fix: Fix): string {
	const C = t.fixJobs.commands;
	return fix.kind === "tunnel_restart" ? C.tunnel_restart(fix.args.unit ?? "") : C[fix.kind];
}
