import { Button, type DataColumn, DataTable, PageHeader } from "@nyxon/nasim";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import type { ServerOut } from "@/api/generated/model";
import { useCanManage } from "@/features/auth";
import { AddIcon } from "@/shared/icons";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { formatPercent, formatRelativeTime, t } from "@/strings";
import { useServers } from "../api";
import { displayName, roleLabel } from "../lib/status";
import { AddServerDialog } from "./AddServerDialog";
import { ServerStatusChip } from "./ServerStatusChip";

const columns: DataColumn<ServerOut>[] = [
	{
		id: "name",
		header: t.servers.name,
		isRowHeader: true,
		cell: (server) => (
			<Link
				to="/servers/$serverId"
				params={{ serverId: String(server.id) }}
				className="font-semibold text-accent-soft-foreground underline-offset-4 hover:underline"
			>
				{displayName(server)}
			</Link>
		),
	},
	{ id: "role", header: t.servers.role, cell: (server) => roleLabel(server.role) },
	{
		id: "status",
		header: t.servers.status,
		cell: (server) => <ServerStatusChip status={server.status} />,
	},
	{
		id: "ip",
		header: t.servers.ip,
		cell: (server) => (
			<span dir="ltr" className="font-mono">
				{server.public_ip ?? t.common.none}
			</span>
		),
	},
	{
		id: "cpu",
		header: t.servers.cpu,
		cell: (server) =>
			server.latest.cpu_pct == null ? t.common.none : formatPercent(server.latest.cpu_pct),
	},
	{
		id: "ram",
		header: t.servers.ram,
		cell: (server) =>
			server.latest.ram_pct == null ? t.common.none : formatPercent(server.latest.ram_pct),
	},
	{
		id: "seen",
		header: t.servers.lastSeen,
		cell: (server) =>
			server.last_seen ? formatRelativeTime(server.last_seen) : t.servers.neverSeen,
	},
];

export function ServersPage() {
	useDocumentTitle(t.servers.title);
	const servers = useServers();
	const canManage = useCanManage();
	const [adding, setAdding] = useState(false);
	return (
		<div className="flex flex-col gap-6">
			<PageHeader
				title={t.servers.title}
				description={t.servers.subtitle}
				actions={
					canManage ? (
						<Button onPress={() => setAdding(true)}>
							<AddIcon aria-hidden />
							{t.servers.add}
						</Button>
					) : undefined
				}
			/>
			<DataTable
				ariaLabel={t.servers.tableLabel}
				columns={columns}
				rows={servers.data}
				getRowId={(server) => String(server.id)}
				status={servers.isPending ? "loading" : servers.isError ? "error" : "ready"}
				onRetry={() => void servers.refetch()}
				emptyTitle={t.servers.emptyTitle}
				empty={t.servers.empty}
				cards="md"
			/>
			<AddServerDialog isOpen={adding} onOpenChange={setAdding} />
		</div>
	);
}
