import {
	Button,
	type DataColumn,
	DataTable,
	EmptyState,
	SectionCard,
	SkeletonRows,
	StatusChip,
} from "@nyxon/nasim";
import { useState } from "react";
import type { PlaybookItem } from "@/api/generated/model";
import { Loadable } from "@/shared/Loadable";
import { t } from "@/strings";
import { usePlaybooks } from "../api";
import { PlaybookModal } from "./PlaybookModal";

const P = t.reports.playbooks;

export function PlaybooksTab() {
	const playbooks = usePlaybooks();
	const [open, setOpen] = useState<string | null>(null);
	const columns: DataColumn<PlaybookItem>[] = [
		{
			id: "code",
			header: P.columns.code,
			isRowHeader: true,
			cell: (row) => (
				<span dir="ltr" className="font-mono text-sm font-semibold">
					{row.code}
				</span>
			),
		},
		{
			id: "title",
			header: P.columns.title,
			cell: (row) => (
				<span dir="ltr" className="block min-w-40 max-w-52 whitespace-normal text-start text-sm">
					{row.title}
				</span>
			),
		},
		{
			id: "detector",
			header: P.columns.detector,
			cell: (row) => (
				<StatusChip
					tone={row.detector === "live" ? "success" : "neutral"}
					label={(P.detector as Record<string, string>)[row.detector] ?? row.detector}
					size="sm"
				/>
			),
		},
		{
			id: "summary",
			header: P.columns.summary,
			cell: (row) => (
				<span className="block min-w-56 max-w-72 whitespace-normal text-sm text-muted">
					{row.summary_fa}
				</span>
			),
		},
		{
			id: "open",
			header: <span className="sr-only">{P.open}</span>,
			isActions: true,
			cell: (row) => (
				<Button
					size="sm"
					variant="secondary"
					aria-label={P.openLabel(row.code)}
					onPress={() => setOpen(row.code)}
				>
					{P.open}
				</Button>
			),
		},
	];
	return (
		<SectionCard title={t.reports.tabs.playbooks}>
			<Loadable query={playbooks} skeleton={<SkeletonRows />}>
				{(data) =>
					data.playbooks.length === 0 ? (
						<EmptyState title={P.emptyTitle} description={P.empty} />
					) : (
						<DataTable<PlaybookItem>
							ariaLabel={P.tableLabel}
							getRowId={(row) => row.code}
							rows={data.playbooks}
							columns={columns}
							status="ready"
						/>
					)
				}
			</Loadable>
			<PlaybookModal code={open} onClose={() => setOpen(null)} />
		</SectionCard>
	);
}
