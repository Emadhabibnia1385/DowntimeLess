import {
	type DataColumn,
	DataTable,
	EmptyState,
	SearchBox,
	SectionCard,
	SelectField,
	SkeletonRows,
	StatCard,
	StatusChip,
} from "@nyxon/nasim";
import { useState } from "react";
import type { HealthOut, ServerHealth } from "@/api/generated/model";
import { ServerLabel } from "@/features/issues";
import { Loadable } from "@/shared/Loadable";
import { flagOf, formatNumber, t } from "@/strings";
import { useHealth } from "../api";
import {
	type Band,
	BANDS,
	bandTone,
	filterHealth,
	nextSort,
	type SortKey,
	type SortState,
	sortHealth,
} from "../lib/health";
import { SortButton } from "./SortButton";

const H = t.reports.health;
const BAND_LABELS: Record<string, string> = H.bands;
const PENALTY: Record<string, string> = H.penalty;
const GATE: Record<string, string> = H.gate;
const bandOptions = [
	{ value: "all", label: H.bandAll },
	...BANDS.map((value) => ({ value, label: BAND_LABELS[value] })),
];

function Stats({ counts }: { counts: HealthOut["counts"] }) {
	return (
		<section aria-label={H.statsLabel} className="grid grid-cols-2 gap-3 md:grid-cols-4">
			{BANDS.map((band) => (
				<StatCard key={band} label={BAND_LABELS[band]} value={formatNumber(counts[band] ?? 0)} />
			))}
		</section>
	);
}

function Why({ row }: { row: ServerHealth }) {
	if (row.gates.length === 0 && row.penalties.length === 0) {
		return <span className="text-muted">{row.score === null ? t.common.none : H.noPenalties}</span>;
	}
	return (
		<ul className="flex min-w-56 flex-col gap-1 text-sm">
			{row.gates.map((gate) => (
				<li key={gate.key} className="flex items-center gap-2">
					<StatusChip tone="danger" label={GATE[gate.key] ?? gate.key} size="sm" />
				</li>
			))}
			{row.penalties.map((penalty) => (
				<li key={penalty.key} className="flex justify-between gap-3">
					<span>{PENALTY[penalty.key] ?? penalty.key}</span>
					<span className="tabular-nums text-muted">−{formatNumber(penalty.points)}</span>
				</li>
			))}
		</ul>
	);
}

export function HealthTab() {
	const health = useHealth();
	const [query, setQuery] = useState("");
	const [band, setBand] = useState<Band | "all">("all");
	const [sort, setSort] = useState<SortState>(null);
	const onSort = (key: SortKey) => setSort((prev) => nextSort(prev, key));
	const head = (label: string, key: SortKey) => (
		<SortButton label={label} sortKey={key} sort={sort} onSort={onSort} />
	);
	const columns: DataColumn<ServerHealth>[] = [
		{
			id: "server",
			header: head(H.columns.server, "name"),
			isRowHeader: true,
			cell: (row) => (
				<ServerLabel serverId={row.server_id} name={row.name} flag={flagOf(row.country)} />
			),
		},
		{
			id: "band",
			header: head(H.columns.band, "band"),
			cell: (row) => (
				<StatusChip tone={bandTone(row.band)} label={BAND_LABELS[row.band] ?? row.band} size="sm" />
			),
		},
		{
			id: "score",
			header: head(H.columns.score, "score"),
			align: "end",
			cell: (row) => (
				<span className="tabular-nums font-semibold">
					{row.score === null ? t.common.none : formatNumber(row.score)}
				</span>
			),
		},
		{
			id: "role",
			header: H.columns.role,
			cell: (row) => (t.roles as Record<string, string>)[row.role] ?? row.role,
		},
		{ id: "why", header: H.columns.penalties, cell: (row) => <Why row={row} /> },
	];
	return (
		<Loadable query={health} skeleton={<SkeletonRows />}>
			{(data) => {
				if (data.servers.length === 0) {
					return <EmptyState title={H.emptyTitle} description={H.empty} />;
				}
				const rows = sortHealth(filterHealth(data.servers, { query, band }), sort);
				return (
					<div className="flex flex-col gap-6">
						<Stats counts={data.counts} />
						<SectionCard title={t.reports.tabs.health}>
							<div className="flex flex-col gap-4">
								<div className="grid max-w-xl items-end gap-3 sm:grid-cols-2">
									<SearchBox
										label={H.search}
										placeholder={H.searchPlaceholder}
										value={query}
										onChange={setQuery}
									/>
									<SelectField
										label={H.bandField}
										value={band}
										onChange={(next) => setBand((next ?? "all") as Band | "all")}
										options={bandOptions}
									/>
								</div>
								{rows.length === 0 ? (
									<EmptyState title={H.noMatchTitle} description={H.noMatch} />
								) : (
									<DataTable<ServerHealth>
										ariaLabel={H.tableLabel}
										getRowId={(row) => String(row.server_id)}
										rows={rows}
										columns={columns}
										status="ready"
									/>
								)}
							</div>
						</SectionCard>
					</div>
				);
			}}
		</Loadable>
	);
}
