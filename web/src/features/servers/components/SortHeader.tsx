import type { SortDirection, SortKey, SortState } from "../lib/sort";
import { t } from "@/strings";

// A column title that sorts the table when pressed, with an arrow on the sorted one.
export function SortHeader({
	label,
	unit,
	sortKey,
	first = "desc",
	sort,
	onSort,
}: {
	label: string;
	unit?: string;
	sortKey: SortKey;
	first?: SortDirection;
	sort: SortState;
	onSort: (key: SortKey, first: SortDirection) => void;
}) {
	const active = sort?.key === sortKey ? sort.direction : null;
	return (
		<button
			type="button"
			aria-label={t.servers.sortBy(label)}
			onClick={() => onSort(sortKey, first)}
			className="inline-flex cursor-pointer items-center gap-1 rounded px-1 font-semibold outline-none hover:text-foreground focus-visible:outline-2 focus-visible:outline-focus"
		>
			<span className="flex max-w-20 flex-col items-start whitespace-normal text-start leading-tight">
				{label}
				{unit ? (
					<span className="whitespace-nowrap text-xs font-normal text-muted">{unit}</span>
				) : null}
			</span>
			<span aria-hidden className={active ? "text-accent" : "text-muted opacity-50"}>
				{active === "asc" ? "▲" : active === "desc" ? "▼" : "↕"}
			</span>
		</button>
	);
}
