import { Button, type DataColumn, DataTable, FilterChips, PageHeader } from "@nyxon/nasim";
import { type ReactNode, useMemo, useState } from "react";
import type { ServerOut } from "@/api/generated/model";
import { useCanManage } from "@/features/auth";
import { CategoryManager, useCategories } from "@/features/categories";
import { AddIcon, ArrowDownIcon, ArrowUpIcon } from "@/shared/icons";
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

// Download and upload side by side, then "=" and their sum.
function TrafficCell({ rx, tx }: { rx: number | null | undefined; tx: number | null | undefined }) {
	if (rx == null && tx == null) return t.common.none;
	return (
		<div className="flex items-center justify-center gap-2 whitespace-nowrap">
			<span title={t.servers.download} className="inline-flex items-center gap-0.5">
				<ArrowDownIcon aria-hidden className="size-3.5 text-muted" />
				{rate(rx)}
			</span>
			<span title={t.servers.upload} className="inline-flex items-center gap-0.5">
				<ArrowUpIcon aria-hidden className="size-3.5 text-muted" />
				{rate(tx)}
			</span>
			<span className="inline-flex items-center gap-1 font-semibold">
				<span aria-hidden>=</span>
				{rate((rx ?? 0) + (tx ?? 0))}
			</span>
		</div>
	);
}

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

const ALL = "all";
const NONE = "none";
const ROLE_ORDER = ["relay", "exit", "panel", "panel_only", "other"];

export function ServersPage() {
	useDocumentTitle(t.servers.title);
	const servers = useServers();
	const canManage = useCanManage();
	const [adding, setAdding] = useState(false);
	const [sort, setSort] = useState<SortState>(null);
	const categories = useCategories();
	const [managing, setManaging] = useState(false);
	const [filter, setFilter] = useState<string>(ALL);
	const names = useMemo(
		() => new Map((categories.data ?? []).map((category) => [category.id, category.name])),
		[categories.data],
	);
	const hasUncategorized = (servers.data ?? []).some((server) => server.category_id == null);
	const options = [
		{ value: ALL, label: t.categories.filterAll },
		...(categories.data ?? []).map((category) => ({
			value: String(category.id),
			label: category.name,
		})),
		...(hasUncategorized && names.size > 0 ? [{ value: NONE, label: t.categories.none }] : []),
	];
	const fleet = options.some((option) => option.value === filter) ? filter : ALL;
	const [roleChoice, setRoleChoice] = useState<string>(ALL);
	const rolesPresent = ROLE_ORDER.filter((role) =>
		(servers.data ?? []).some((server) => server.role === role),
	);
	const roleOptions = [
		{ value: ALL, label: t.categories.filterAll },
		...rolesPresent.map((role) => ({ value: role, label: roleLabel(role) })),
	];
	const role = roleOptions.some((option) => option.value === roleChoice) ? roleChoice : ALL;
	const onSort = (key: SortKey, first: SortDirection) =>
		setSort((current) => nextSort(current, key, first));
	const rows = useMemo(
		() =>
			sortServers(
				(servers.data ?? []).filter(
					(server) =>
						(role === ALL || server.role === role) &&
						(fleet === ALL ||
							(fleet === NONE ? server.category_id == null : String(server.category_id) === fleet)),
				),
				sort,
			),
		[servers.data, sort, fleet, role],
	);
	const head = (label: string, key: SortKey, first: SortDirection = "desc", unit?: string) => (
		<SortHeader label={label} unit={unit} sortKey={key} first={first} sort={sort} onSort={onSort} />
	);
	const columnDefs: DataColumn<ServerOut>[] = [
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
				<div className="flex flex-col items-center gap-1">
					<ServerStatusChip status={server.status} />
					<span className="text-xs text-muted">
						{[roleLabel(server.role), names.get(server.category_id ?? -1)]
							.filter(Boolean)
							.join(" · ")}
					</span>
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
			id: "traffic",
			header: head(t.servers.bandwidth, "bandwidth", "desc", t.servers.mbps),
			cell: (s) => <TrafficCell rx={s.latest.rx_bps} tx={s.latest.tx_bps} />,
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
	// every title and cell reads from the middle
	const columns = columnDefs.map((column) => ({ ...column, className: "text-center" }));
	return (
		<div className="flex flex-col gap-6">
			<PageHeader
				title={t.servers.title}
				description={t.servers.subtitle}
				actions={
					canManage ? (
						<>
							<Button onPress={() => setAdding(true)}>
								<AddIcon aria-hidden />
								{t.servers.add}
							</Button>
							<Button variant="secondary" onPress={() => setManaging(true)}>
								{t.categories.manage}
							</Button>
							<UpdateAllAgentsButton servers={servers.data ?? []} />
						</>
					) : undefined
				}
			/>
			<div className="flex flex-wrap items-start gap-x-8 gap-y-3">
				<FilterChips
					label={t.categories.filterLabel}
					value={fleet}
					onChange={setFilter}
					options={options}
				/>
				<FilterChips
					label={t.servers.roleFilterLabel}
					value={role}
					onChange={setRoleChoice}
					options={roleOptions}
				/>
			</div>
			<DataTable
				ariaLabel={t.servers.tableLabel}
				columns={columns}
				rows={rows}
				getRowId={(server) => String(server.id)}
				status={servers.isPending ? "loading" : servers.isError ? "error" : "ready"}
				onRetry={() => void servers.refetch()}
				emptyTitle={t.servers.emptyTitle}
				empty={t.servers.empty}
			/>
			<AddServerDialog isOpen={adding} onOpenChange={setAdding} />
			<CategoryManager isOpen={managing} onOpenChange={setManaging} />
		</div>
	);
}
