import { Link } from "@tanstack/react-router";
import type { ServerOut } from "@/api/generated/model";
import { formatPercent, t } from "@/strings";
import { displayName, roleLabel } from "../lib/status";
import { ServerStatusChip } from "./ServerStatusChip";
import { IpText } from "@/shared/IpText";

const level = (value: number | null | undefined) =>
	value === null || value === undefined ? t.common.none : formatPercent(value);

// One server as a card: the name leads to its page, the numbers are the latest report.
export function ServerCard({ server }: { server: ServerOut }) {
	return (
		<Link
			to="/servers/$serverId"
			params={{ serverId: String(server.id) }}
			className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4 outline-none transition-colors hover:bg-surface-secondary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
		>
			<div className="flex items-start justify-between gap-2">
				<div className="min-w-0">
					<p className="truncate font-semibold">{displayName(server)}</p>
					<p className="text-xs text-muted">{roleLabel(server.role)}</p>
				</div>
				<ServerStatusChip status={server.status} />
			</div>
			<p className="text-sm text-muted">
				{server.public_ip ? <IpText ip={server.public_ip} /> : t.common.none}
			</p>
			<dl className="grid grid-cols-2 gap-2 text-sm">
				<div>
					<dt className="text-xs text-muted">{t.servers.cpu}</dt>
					<dd>{level(server.latest.cpu_pct)}</dd>
				</div>
				<div>
					<dt className="text-xs text-muted">{t.servers.ram}</dt>
					<dd>{level(server.latest.ram_pct)}</dd>
				</div>
			</dl>
		</Link>
	);
}
