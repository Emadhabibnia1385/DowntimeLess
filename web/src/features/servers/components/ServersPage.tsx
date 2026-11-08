import { Button, type DataColumn, DataTable, PageHeader } from "@nyxon/nasim";
import { useMemo, useState } from "react";
import type { ServerOut } from "@/api/generated/model";
import { useCanManage } from "@/features/auth";
import { AddIcon } from "@/shared/icons";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { formatNumber, formatPercent, t } from "@/strings";
import { useServers } from "../api";
import {
	nextSort,
	type SortDirection,
	type SortKey,
	type SortState,
	sortServers,
} from "../lib/sort";
import { roleLabel } from "../lib/status";
import { AddServerDialog } from "./AddServerDialog";
import { ServerNameCell } from "./ServerNameCell";
import { ServerRowActions } from "./ServerRowActions";
import { ServerStatusChip } from "./ServerStatusChip";
import { SortHeader } from "./SortHeader";
import { UpdateAllAgentsButton } from "./UpdateAllAgentsButton";

const percent = (value: number | null | undefined) =>
	value == null ? t.common.none : formatPercent(value);
const rate = (value: number | null | undefined) =>
	value == null ? t.common.none : formatNumber(Math.round(value / 1_000_000));

// What a row says about its agent: the version, and whether the panel holds a newer one.
const agentCell = (server: ServerOut) => {
	if (!server.agent_version) return t.common.none;
	return (
		<span
			dir="ltr"
			title={server.agent_outdated ? t.servers.agentOutdated(server.agent_version) : undefined}
			className={server.agent_outdated ? "font-mono text-warning" : "font-mono"}
		>
			{server.agent_version}
		</span>
	);
};

export function ServersPage() {
	useDocumentTitle(t.servers.title);
	const servers = useServers();
	const canManage = useCanManage();
	const [adding, setAdding] = useState(false);
	const [sort, setSort] = useState<SortState>(null);
	const onSort = (key: SortKey, first: SortDirection) =>
		setSort((current) => nextSort(current, key, first));
	const rows = useMemo(() => sortServers(servers.data ?? [], sort), [servers.data, sort]);
	const head = (label: string, key: SortKey, first: SortDirection = "desc") => (
		<SortHeader label={label} sortKey={key} first={first} sort={sort} onSort={onSort} />
	);
	const columns: DataColumn<ServerOut>[] = [
		{
			id: "name",
			header: head(t.servers.name, "name", "asc"),
			isRowHeader: true,
			cell: (server) => <ServerNameCell server={server} />,
		},
		{
			id: "role",
			header: head(t.servers.role, "role", "asc"),
			cell: (server) => roleLabel(server.role),
		},
		{
			id: "status",
			header: head(t.servers.status, "status", "asc"),
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
		{ id: "cpu", header: head(t.servers.cpu, "cpu"), cell: (s) => percent(s.latest.cpu_pct) },
		{ id: "ram", header: head(t.servers.ram, "ram"), cell: (s) => percent(s.latest.ram_pct) },
		{
			id: "steal",
			header: head(t.servers.steal, "steal"),
			cell: (s) => percent(s.latest.steal_pct),
		},
		{
			id: "download",
			header: head(t.servers.download, "download"),
			cell: (s) => rate(s.latest.rx_bps),
		},
		{
			id: "upload",
			header: head(t.servers.upload, "upload"),
			cell: (s) => rate(s.latest.tx_bps),
		},
		{
			id: "retrans",
			header: head(t.servers.retrans, "retrans"),
			cell: (s) => percent(s.latest.tcp_retrans_pct),
		},
		{ id: "agent", header: t.servers.agent, cell: agentCell },
		...(canManage
			? [
					{
						id: "actions",
						header: t.servers.actions,
						isActions: true,
						cell: (server: ServerOut) => <ServerRowActions server={server} />,
					},
				]
			: []),
	];
	return (
		<div className="flex flex-col gap-6">
			<PageHeader
				title={t.servers.title}
				description={t.servers.subtitle}
				actions={
					canManage ? (
						<>
							<UpdateAllAgentsButton servers={servers.data ?? []} />
							<Button onPress={() => setAdding(true)}>
								<AddIcon aria-hidden />
								{t.servers.add}
							</Button>
						</>
					) : undefined
				}
			/>
			<DataTable
				ariaLabel={t.servers.tableLabel}
				columns={columns}
				rows={rows}
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
