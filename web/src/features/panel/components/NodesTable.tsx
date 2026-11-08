import { type DataColumn, DataTable, StatusChip } from "@nyxon/nasim";
import type { PanelNode } from "@/api/generated/model";
import { formatBytes, formatNumber, formatPercent, t } from "@/strings";
import { nodeTone, shareOf, shareTone } from "../lib/view";
import { IgnoreButton } from "./IgnoreButton";

const N = t.panel.nodes;
const STATUS: Record<string, string> = N.status;

function NameCell({ node }: { node: PanelNode }) {
	return (
		<div className="flex flex-col items-start gap-0.5">
			<span className="font-medium">{node.name}</span>
			{node.address ? (
				<span dir="ltr" className="font-mono text-xs text-muted">
					{node.port ? `${node.address}:${node.port}` : node.address}
				</span>
			) : null}
			{node.message ? <span className="text-xs text-muted">{node.message}</span> : null}
		</div>
	);
}

function StatusCell({ node }: { node: PanelNode }) {
	const label = node.ignored ? N.retired : (STATUS[node.status] ?? STATUS.unknown);
	return (
		<div className="flex flex-wrap gap-1.5">
			<StatusChip tone={nodeTone(node)} label={label} size="sm" />
			{node.dropped && !node.ignored ? (
				<StatusChip tone="warning" label={N.dropped} size="sm" />
			) : null}
		</div>
	);
}

// Each node: status, last full hour's users and bytes, and that hour against its own median.
export function NodesTable({
	serverId,
	nodes,
	dropAt,
	canManage,
}: {
	serverId: number;
	nodes: readonly PanelNode[];
	dropAt: number;
	canManage: boolean;
}) {
	const columns: DataColumn<PanelNode>[] = [
		{
			id: "name",
			header: N.columns.name,
			isRowHeader: true,
			cell: (node) => <NameCell node={node} />,
		},
		{ id: "status", header: N.columns.status, cell: (node) => <StatusCell node={node} /> },
		{
			id: "users",
			header: N.columns.users,
			align: "end",
			cell: (node) =>
				node.users_last == null ? (
					t.common.none
				) : (
					<span className="tabular-nums">{formatNumber(node.users_last)}</span>
				),
		},
		{
			id: "bytes",
			header: N.columns.bytes,
			align: "end",
			cell: (node) =>
				node.bytes_last == null ? (
					t.common.none
				) : (
					<span className="tabular-nums">{formatBytes(node.bytes_last)}</span>
				),
		},
		{
			id: "median",
			header: N.columns.median,
			cell: (node) => {
				const share = shareOf(node);
				if (share === null) return <span className="text-xs text-muted">{N.noMedian}</span>;
				return (
					<StatusChip tone={shareTone(share, dropAt)} label={formatPercent(share)} size="sm" />
				);
			},
		},
		...(canManage
			? [
					{
						id: "actions",
						header: N.columns.actions,
						isActions: true,
						cell: (node: PanelNode) => (
							<IgnoreButton
								serverId={serverId}
								kind="node"
								name={String(node.id)}
								ignored={node.ignored}
								label={node.ignored ? N.unretire : N.retire}
								ariaLabel={(node.ignored ? N.unretireLabel : N.retireLabel)(node.name)}
							/>
						),
					},
				]
			: []),
	];
	return (
		<DataTable
			ariaLabel={N.tableLabel}
			columns={columns}
			rows={nodes}
			getRowId={(node) => String(node.id)}
			status="ready"
			emptyTitle={N.empty}
		/>
	);
}
