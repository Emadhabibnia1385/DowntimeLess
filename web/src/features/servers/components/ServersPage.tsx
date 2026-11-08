import { Button, type DataColumn, DataTable, FilterChips, PageHeader } from "@nyxon/nasim";
import { type ReactNode, useMemo, useState } from "react";
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
import { cpuUsage, diskUsage, ramUsage, type Usage } from "../lib/usage";
import { AddServerDialog } from "./AddServerDialog";
import { ServerNameCell } from "./ServerNameCell";
import { ServerRowActions } from "./ServerRowActions";
import { ServerStatusChip } from "./ServerStatusChip";
import { PlainHeader, SortHeader } from "./SortHeader";
import { UpdateAllAgentsButton } from "./UpdateAllAgentsButton";

const percent = (value: number | null | undefined) =>
	value == null ? t.common.none : formatPercent(value);
const rate = (value: number | null | undefined) =>
	value == null ? t.common.none : formatNumber(Math.round(value / 1_000_000));
const bandwidth = (rx: number | null | undefined, tx: number | null | undefined) =>
	rx == null && tx == null ? t.common.none : rate((rx ?? 0) + (tx ?? 0));

// A level as its percent with, under it, what that means in cores or gigabytes.
const usageCell = (usage: Usage | null): ReactNode =>
	usage ? (
		<div className="leading-tight">
			<p>{usage.percent}</p>
			{usage.detail ? <p className="text-xs text-muted">{usage.detail}</p> : null}
		</div>
	) : (
		t.common.none
	);

const FLEET_FILTERS = ["all", "emad", "mobin", "shared"] as const;

export function ServersPage() {
	useDocumentTitle(t.servers.title);
	const servers = useServers();
	const canManage = useCanManage();
	const [adding, setAdding] = useState(false);
	const [sort, setSort] = useState<SortState>(null);
	const [fleet, setFleet] = useState<string>("all");
	const onSort = (key: SortKey, first: SortDirection) =>
		setSort((current) => nextSort(current, key, first));
	const rows = useMemo(
		() =>
			sortServers(
				(servers.data ?? []).filter((server) => fleet === "all" || server.fleet === fleet),
				sort,
			),
		[servers.data, sort, fleet],
	);
	const head = (label: string, key: SortKey, first: SortDirection = "desc", unit?: string) => (
		<SortHeader label={label} unit={unit} sortKey={key} first={first} sort={sort} onSort={onSort} />
	);
	const columns: DataColumn<ServerOut>[] = [
		{
			id: "name",
			header: head(t.servers.name, "name", "asc"),
			isRowHeader: true,
			cell: (server) => <ServerNameCell server={server} />,
		},
		{
			id: "status",
			header: head(t.servers.status, "status", "asc"),
			cell: (server) => (
				<div className="flex flex-col items-start gap-1">
					<ServerStatusChip status={server.status} />
					<span className="text-xs text-muted">{roleLabel(server.role)}</span>
				</div>
			),
		},
		{
			id: "cpu",
			header: head(t.servers.cpu, "cpu"),
			cell: (s) => usageCell(cpuUsage(s.latest)),
		},
		{
			id: "ram",
			header: head(t.servers.ram, "ram"),
			cell: (s) => usageCell(ramUsage(s.latest)),
		},
		{
			id: "disk",
			header: head(t.servers.disk, "disk"),
			cell: (s) => usageCell(diskUsage(s.latest)),
		},
		{
			id: "steal",
			header: head(t.servers.steal, "steal"),
			cell: (s) => percent(s.latest.steal_pct),
		},
		{
			id: "download",
			header: head(t.servers.download, "download", "desc", t.servers.mbps),
			cell: (s) => rate(s.latest.rx_bps),
		},
		{
			id: "upload",
			header: head(t.servers.upload, "upload", "desc", t.servers.mbps),
			cell: (s) => rate(s.latest.tx_bps),
		},
		{
			id: "bandwidth",
			header: head(t.servers.bandwidth, "bandwidth", "desc", t.servers.mbps),
			cell: (s) => bandwidth(s.latest.rx_bps, s.latest.tx_bps),
		},
		{
			id: "retrans",
			header: head(t.servers.retrans, "retrans"),
			cell: (s) => percent(s.latest.tcp_retrans_pct),
		},
		...(canManage
			? [
					{
						id: "actions",
						header: <PlainHeader label={t.servers.actions} help={t.servers.help.actions} />,
						isActions: true,
						cell: (server: ServerOut) => <ServerRowActions server={server} />,
					},
				]
			: []),
	];
	const filterOptions = FLEET_FILTERS.map((value) => ({
		value,
		label: value === "all" ? t.servers.filterAll : t.servers.fleets[value],
	}));
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
			<FilterChips
				label={t.servers.filterLabel}
				value={fleet}
				onChange={setFleet}
				options={filterOptions}
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
