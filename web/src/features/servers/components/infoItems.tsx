import { Chip } from "@nyxon/nasim";
import type { ReactNode } from "react";
import type { ServerOut } from "@/api/generated/model";
import { IpText } from "@/shared/IpText";
import {
	formatBytes,
	formatDateTime,
	formatDuration,
	formatNumber,
	formatPercent,
	formatRelativeTime,
	ipv4Of,
	t,
} from "@/strings";
import { datacenterOf, whereOf } from "../lib/where";
import { roleLabel } from "../lib/status";
import { AgentVersionMark } from "./AgentVersionMark";

type Item = { label: string; value: ReactNode; ltr?: boolean };

const MB = 1024 ** 2;
const GB = 1024 ** 3;
const none = t.common.none;
const technical = (text: string, mono = false) => (
	<bdi dir="ltr" className={mono ? "font-mono" : undefined}>
		{text}
	</bdi>
);

function swapText(server: ServerOut): string | null {
	const { swap_total_mb: total, swap_pct: pct } = server.latest;
	if (!total) return null;
	return pct == null
		? formatBytes(total * MB)
		: `${formatBytes(total * MB)} · ${formatPercent(pct)}`;
}

/** The details rows; one with no value is left out, except place, data center and IP. */
export function infoItems(server: ServerOut, categoryName?: string): (Item | false | null)[] {
	const { latest, system } = server;
	const { flag, place } = whereOf({ ...server, org: null });
	const ip = ipv4Of(server.public_ip);
	const datacenter = datacenterOf(server);
	const cores = system?.cpu_cores ?? latest.cpu_cores;
	const coresText = cores ? t.server.cpuCores(formatNumber(cores)) : null;
	const swap = swapText(server);
	return [
		{
			label: t.server.location,
			value: place ? (
				<span className="inline-flex items-center gap-1.5">
					<span aria-hidden className="text-lg leading-none">
						{flag}
					</span>
					{technical(place)}
				</span>
			) : (
				none
			),
		},
		{ label: t.server.datacenter, value: datacenter ? technical(datacenter) : none },
		{ label: t.server.ip, value: ip ? <IpText ip={ip} /> : none },
		!!system?.ipv6 && { label: t.server.ipv6, value: <IpText ip={system.ipv6} /> },
		!!server.hostname && { label: t.server.hostname, value: technical(server.hostname, true) },
		!!system?.os && { label: t.server.os, value: technical(system.os) },
		!!system?.kernel && { label: t.server.kernel, value: technical(system.kernel, true) },
		(!!coresText || !!system?.cpu_model) && {
			label: t.server.cpuModel,
			value: (
				<span>
					{coresText}
					{coresText && system?.cpu_model ? " · " : null}
					{system?.cpu_model ? technical(system.cpu_model) : null}
				</span>
			),
		},
		!!latest.ram_total_mb && {
			label: t.server.ramTotal,
			value: formatBytes(latest.ram_total_mb * MB),
		},
		!!latest.disk_total_gb && {
			label: t.server.diskTotal,
			value: formatBytes(latest.disk_total_gb * GB),
		},
		!!swap && { label: t.server.swap, value: swap },
		!!system?.boot_ts && { label: t.server.boot, value: formatDateTime(system.boot_ts) },
		latest.uptime_s != null && { label: t.server.uptime, value: formatDuration(latest.uptime_s) },
		!!server.agent_version && {
			label: t.server.agentVersion,
			value: (
				<span className="inline-flex items-center gap-1">
					<span dir="ltr" className="font-mono">
						{server.agent_version}
					</span>
					<AgentVersionMark outdated={Boolean(server.agent_outdated)} />
				</span>
			),
		},
		{
			label: t.server.lastSeen,
			value: server.last_seen
				? t.server.lastSeenAt(
						formatRelativeTime(server.last_seen),
						formatDateTime(server.last_seen),
					)
				: t.servers.neverSeen,
		},
		{ label: t.server.role, value: roleLabel(server.role) },
		!!categoryName && { label: t.server.category, value: categoryName },
		!!server.quota_gb && {
			label: t.server.quota,
			value: (
				<span className="inline-flex flex-wrap items-center gap-1.5">
					{t.server.quotaValue(formatNumber(server.quota_gb))}
					{server.count_upload === false ? (
						<Chip size="sm" variant="soft">
							{t.server.uploadFree}
						</Chip>
					) : null}
				</span>
			),
		},
	];
}
