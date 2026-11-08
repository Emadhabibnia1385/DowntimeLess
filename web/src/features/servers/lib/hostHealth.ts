import type { HostHealth } from "@/api/generated/model";
import { formatDecimal, formatDuration, formatNumber, formatPercent, t } from "@/strings";

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";
export type HealthRow = { key: string; label: string; tone: Tone; state: string; detail: string };

const H = t.server.hostHealth;
const UP = new Set(["active", "activating", "reloading", "refreshing"]);
const LONG_TIMEOUT_S = 43200;
const INODE_WARN = 85;
const sep = "، ";

function listeners(h: HostHealth): HealthRow | null {
	const l = h.listeners;
	if (!l) return null;
	const alerting = l.missing.filter((port) => port.alerting);
	const parts = [H.listenersCount(formatNumber(l.current), formatNumber(l.baseline))];
	if (l.learning) parts.push(H.learning(formatNumber(l.learning)));
	if (l.missing.length) {
		parts.push(
			H.missing(
				l.missing.map((p) => `${p.proto}/${p.port}${p.proc ? ` (${p.proc})` : ""}`).join(sep),
			),
		);
	}
	const tone: Tone = alerting.length ? "danger" : l.missing.length ? "warning" : "success";
	return {
		key: "listeners",
		label: H.rows.listeners,
		tone,
		state: H.states[tone],
		detail: parts.join(" · "),
	};
}

function units(h: HostHealth): HealthRow | null {
	const tunnel = (h.units ?? []).filter((u) => u.tunnel);
	if (!h.units) return null;
	const stopped = tunnel.filter(
		(u) => u.enabled && !UP.has(u.active ?? "") && u.sub !== "auto-restart",
	);
	const looping = tunnel.filter((u) => u.sub === "auto-restart" || u.restarts_10m >= 3);
	const running = tunnel.length - stopped.length - looping.length;
	const parts = [H.unitsCount(formatNumber(Math.max(0, running)), formatNumber(tunnel.length))];
	if (stopped.length) parts.push(H.stopped(stopped.map((u) => u.name).join(sep)));
	if (looping.length) parts.push(H.looping(looping.map((u) => u.name).join(sep)));
	const tone: Tone = stopped.length
		? "danger"
		: looping.length
			? "warning"
			: tunnel.length
				? "success"
				: "neutral";
	return {
		key: "units",
		label: H.rows.units,
		tone,
		state: tunnel.length ? H.states[tone] : H.none,
		detail: parts.join(" · "),
	};
}

function containers(h: HostHealth): HealthRow | null {
	if (!h.containers) return null;
	const watched = h.containers.filter((c) => !c.retired);
	const running = watched.filter((c) => c.state === "running");
	const down = watched.filter((c) => c.state === "exited" || c.state === "dead");
	const sick = running.filter((c) => c.health === "unhealthy");
	const parts = [H.containersCount(formatNumber(running.length), formatNumber(watched.length))];
	if (down.length) parts.push(H.stopped(down.map((c) => c.name).join(sep)));
	if (sick.length) parts.push(H.unhealthy(sick.map((c) => c.name).join(sep)));
	const retired = h.containers.length - watched.length;
	if (retired) parts.push(H.retired(formatNumber(retired)));
	const tone: Tone = down.length
		? "danger"
		: sick.length
			? "warning"
			: watched.length
				? "success"
				: "neutral";
	return {
		key: "containers",
		label: H.rows.containers,
		tone,
		state: watched.length ? H.states[tone] : H.none,
		detail: parts.join(" · "),
	};
}

function dnat(h: HostHealth): HealthRow | null {
	const n = h.nft;
	if (!n) return null;
	const present = n.relay_dnat || (n.dnat_rules ?? 0) > 0;
	const parts = [present ? H.dnatRules(formatNumber(n.dnat_rules ?? 0)) : H.noDnat];
	if (n.ip_forward !== null && n.ip_forward !== undefined)
		parts.push(n.ip_forward ? H.forwardOn : H.forwardOff);
	const tone: Tone = !present && n.had_dnat ? "danger" : present ? "success" : "neutral";
	return {
		key: "dnat",
		label: H.rows.dnat,
		tone,
		state: present || n.had_dnat ? H.states[tone] : H.none,
		detail: parts.join(" · "),
	};
}

function conntrack(h: HostHealth): HealthRow | null {
	const c = h.conntrack;
	if (!c) return null;
	if (!c.module_loaded)
		return {
			key: "conntrack",
			label: H.rows.conntrack,
			tone: "neutral",
			state: H.none,
			detail: H.noModule,
		};
	const parts: string[] = [];
	if (c.count != null && c.max != null) {
		parts.push(
			H.table(
				formatNumber(c.count),
				formatNumber(c.max),
				c.pct == null ? "" : formatPercent(c.pct),
			),
		);
	}
	if (c.tcp_established_timeout != null)
		parts.push(H.timeout(formatDuration(c.tcp_established_timeout)));
	if (c.insert_failed || c.drop) {
		parts.push(H.drops(formatNumber(c.insert_failed ?? 0), formatNumber(c.drop ?? 0)));
	}
	const tone: Tone =
		(c.pct ?? 0) >= 85
			? "danger"
			: (c.tcp_established_timeout ?? 0) > LONG_TIMEOUT_S
				? "warning"
				: "success";
	return {
		key: "conntrack",
		label: H.rows.conntrack,
		tone,
		state: H.states[tone],
		detail: parts.join(" · "),
	};
}

function kernel(h: HostHealth): HealthRow | null {
	const k = h.kernel;
	if (!k) return null;
	const parts: string[] = [];
	if (k.congestion) parts.push([k.congestion, k.qdisc].filter(Boolean).join("/"));
	if (k.oom_kill != null) parts.push(H.oom(formatNumber(k.oom_kill)));
	if (k.ntp_synced != null) parts.push(k.ntp_synced ? H.timeOk : H.timeBad);
	if (k.inode_pct != null) parts.push(H.inode(formatPercent(k.inode_pct)));
	if (k.journal_mb != null) parts.push(H.journal(formatDecimal(k.journal_mb, 0)));
	if (h.apt?.reboot_required_pkgs)
		parts.push(H.rebootPkgs(formatNumber(h.apt.reboot_required_pkgs)));
	if (h.apt?.dpkg_audit) parts.push(H.dpkg(formatNumber(h.apt.dpkg_audit)));
	const bad =
		k.ntp_synced === false || (k.inode_pct ?? 0) >= INODE_WARN || (h.apt?.dpkg_audit ?? 0) > 0;
	const tone: Tone = bad ? "warning" : "success";
	return {
		key: "kernel",
		label: H.rows.kernel,
		tone,
		state: H.states[tone],
		detail: parts.join(" · "),
	};
}

function security(h: HostHealth): HealthRow | null {
	const s = h.security;
	if (!s) return null;
	const parts: string[] = [];
	if (s.sshd_ports?.length) parts.push(H.sshd(s.sshd_ports.join(sep)));
	if (s.password_auth != null) parts.push(s.password_auth ? H.passwordOn : H.passwordOff);
	if (s.fail2ban) parts.push(H.fail2ban(s.fail2ban));
	if (s.ufw) parts.push(H.ufw(s.ufw));
	const tone: Tone = s.password_auth ? "warning" : "success";
	return {
		key: "security",
		label: H.rows.security,
		tone,
		state: H.states[tone],
		detail: parts.join(" · "),
	};
}

/** The card's rows in after-reboot check order; blocks the agent did not send are left out. */
export function healthRows(h: HostHealth): HealthRow[] {
	return [listeners, units, containers, dnat, conntrack, kernel, security]
		.map((row) => row(h))
		.filter((row): row is HealthRow => row !== null);
}
