import {
	type DataColumn,
	DataTable,
	EmptyState,
	Notice,
	SectionCard,
	SelectField,
	SkeletonRows,
	StatusChip,
} from "@nyxon/nasim";
import { useMemo } from "react";
import type { EventOut } from "@/api/generated/model";
import { ServerLabel } from "./ServerLabel";
import { useServers } from "@/features/servers";
import { Loadable } from "@/shared/Loadable";
import { flagOf, formatDateTime, t } from "@/strings";
import { useChanges } from "../api";
import { describeEvent, EVENT_KINDS, kindLabel, kindTone } from "../lib/events";
import { PERIODS, type Period } from "../lib/tabs";

const C = t.issueChanges;
const periodOptions = (Object.keys(PERIODS) as Period[]).map((value) => ({
	value,
	label: C.periods[value],
}));
const kindOptions = [
	{ value: "all", label: C.kindAll },
	...EVENT_KINDS.map((value) => ({ value, label: C.kinds[value] })),
];

export function ChangesTab({
	period,
	kind,
	onPeriodChange,
	onKindChange,
}: {
	period: Period;
	kind: string;
	onPeriodChange: (period: Period) => void;
	onKindChange: (kind: string) => void;
}) {
	const changes = useChanges(period);
	const servers = useServers();
	const flags = useMemo(
		() => new Map((servers.data ?? []).map((server) => [server.id, flagOf(server.country)])),
		[servers.data],
	);
	const columns: DataColumn<EventOut>[] = [
		{
			id: "time",
			header: C.columns.time,
			isRowHeader: true,
			cell: (row) => <span className="whitespace-nowrap">{formatDateTime(row.ts)}</span>,
		},
		{
			id: "server",
			header: C.columns.server,
			cell: (row) =>
				row.server ? (
					<ServerLabel
						serverId={row.server_id}
						name={row.server}
						flag={row.server_id === null ? "" : (flags.get(row.server_id) ?? "")}
					/>
				) : (
					t.common.none
				),
		},
		{
			id: "kind",
			header: C.columns.kind,
			cell: (row) => <StatusChip tone={kindTone(row.kind)} label={kindLabel(row.kind)} size="sm" />,
		},
		{
			id: "what",
			header: C.columns.what,
			cell: (row) => (
				<span className="block min-w-56 max-w-96 whitespace-normal">{describeEvent(row)}</span>
			),
		},
	];
	return (
		<SectionCard title={t.issueChanges.title}>
			<div className="flex flex-col gap-4">
				<div className="grid max-w-xl items-end gap-3 sm:grid-cols-2">
					<SelectField
						label={C.periodLabel}
						value={period}
						onChange={(next) => onPeriodChange((next ?? "24h") as Period)}
						options={periodOptions}
					/>
					<SelectField
						label={C.kindLabel}
						value={kind}
						onChange={(next) => onKindChange(next ?? "all")}
						options={kindOptions}
					/>
				</div>
				<Loadable query={changes} skeleton={<SkeletonRows />}>
					{(data) => {
						const rows = data.events.filter((event) => kind === "all" || event.kind === kind);
						return (
							<div className="flex flex-col gap-3">
								{data.truncated ? <Notice tone="info">{C.truncated}</Notice> : null}
								{rows.length === 0 ? (
									<EmptyState title={C.emptyTitle} description={C.empty} />
								) : (
									<DataTable<EventOut>
										ariaLabel={C.tableLabel}
										getRowId={(row) => String(row.id)}
										rows={rows}
										columns={columns}
										status="ready"
									/>
								)}
							</div>
						);
					}}
				</Loadable>
			</div>
		</SectionCard>
	);
}
