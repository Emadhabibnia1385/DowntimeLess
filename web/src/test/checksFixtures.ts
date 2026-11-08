// The real panel shape (23 nodes, 40 resellers, real user counts) and a relay's host checks.
import type { HostHealth, PanelOut, Reseller } from "@/api/generated/model";

const GIB = 1024 ** 3;
const NOW = Math.floor(Date.now() / 1000);

export function panelFixture(over: Partial<PanelOut["panels"][number]> = {}): PanelOut {
	const nodes = Array.from({ length: 23 }, (_, index) => {
		const id = index + 1;
		return {
			id,
			name: `node-${String(id).padStart(2, "0")}`,
			address: `198.51.100.${100 + id}`,
			port: 62050,
			status: id === 23 ? "disabled" : "connected",
			message: null,
			enabled: id !== 23,
			ignored: false,
			users_last: id === 23 ? 0 : id === 6 ? 70 : 300,
			bytes_last: 40 * GIB,
			users_median: 300,
			bytes_median: 40 * GIB,
			users_pct: id === 6 ? 23.3 : 100,
			bytes_pct: 100,
			others_pct: id === 6 ? 100 : null,
			dropped: id === 6,
			down_s: null,
			unavailable_10m: 0,
		};
	});
	const resellers: Reseller[] = Array.from({ length: 40 }, (_, index) => {
		const limit = (200 + 10 * index) * GIB;
		const share =
			index === 3 || index === 17 ? 0.97 : index === 25 ? 0.965 : 0.5 + (index % 7) * 0.05;
		const pct = Math.round(share * 1000) / 10;
		return {
			name: `reseller${String(index).padStart(2, "0")}`,
			used: Math.round(limit * share),
			limit,
			used_pct: pct,
			per_hour: index === 3 ? 2 * GIB : null,
			hours_left: index === 3 ? 3.5 : null,
			level: pct >= 95 ? "critical" : pct >= 85 ? "warning" : "ok",
		};
	});
	return {
		generated_at: NOW,
		reseller_warn: 85,
		reseller_crit: 95,
		node_drop_pct: 30,
		panels: [
			{
				server_id: 9,
				server_name: "panel-1",
				reported_at: NOW - 20,
				version: "5.6.0",
				errors: [],
				panel_error: null,
				available: true,
				hour_start: NOW - (NOW % 3600) - 3600,
				nodes,
				resellers: resellers.sort((a, b) => b.used_pct - a.used_pct),
				user_status: {
					active: 8410,
					limited: 2331,
					expired: 2514,
					on_hold: 291,
					disabled: 24,
					other: 0,
				},
				inbounds_without_group: [{ tag: "wg0", ignored: false }],
				...over,
			},
		],
	};
}

export function hostHealthFixture(over: Partial<HostHealth> = {}): HostHealth {
	return {
		server_id: 1,
		has_checks: true,
		agent_version: "0.3.1",
		checks_error: [],
		listeners: {
			current: 4,
			baseline: 5,
			learning: 0,
			missing: [{ proto: "tcp", port: 443, proc: "xray", missing_reports: 3, alerting: true }],
		},
		units: [
			{
				name: "backhaul-de.service",
				enabled: true,
				active: "inactive",
				sub: "dead",
				restarts: 0,
				restarts_10m: 0,
				tunnel: true,
			},
			{
				name: "relay-dnat.service",
				enabled: true,
				active: "active",
				sub: "exited",
				restarts: 0,
				restarts_10m: 0,
				tunnel: true,
			},
			{
				name: "nginx.service",
				enabled: true,
				active: "active",
				sub: "running",
				restarts: 0,
				restarts_10m: 0,
				tunnel: false,
			},
		],
		containers: [
			{
				name: "pasarguard-node-1",
				image: "pasarguard/node:latest",
				state: "running",
				health: null,
				restarts: 0,
				policy: "always",
				retired: false,
			},
			{
				name: "panel-old",
				image: "pasarguard/panel:latest",
				state: "exited",
				health: null,
				restarts: 2,
				policy: "always",
				retired: false,
			},
		],
		nft: { relay_dnat: true, dnat_rules: 12, tables: 2, ip_forward: 1, had_dnat: true },
		conntrack: {
			module_loaded: true,
			count: 12000,
			max: 1048576,
			pct: 1.1,
			tcp_established_timeout: 432000,
			insert_failed: 0,
			drop: 0,
			early_drop: 0,
		},
		kernel: {
			congestion: "bbr",
			qdisc: "fq",
			ip_forward: 1,
			oom_kill: 0,
			ntp_synced: true,
			inode_pct: 12,
			journal_mb: 300,
			mtu_probing: 0,
			swappiness: 10,
		},
		apt: { dpkg_audit: 0, reboot_required_pkgs: 0, held_docker: false },
		security: { ufw: "inactive", fail2ban: "active", password_auth: false, sshd_ports: [22] },
		...over,
	};
}
