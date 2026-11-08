import { Button } from "@nyxon/nasim";
import { t } from "@/strings";
import type { SortDirection, SortKey, SortState } from "../lib/rows";

// A column title that sorts when pressed and shows the direction beside it.
export function SortHead({
	label,
	sortKey,
	first = "desc",
	sort,
	onSort,
}: {
	label: string;
	sortKey: SortKey;
	first?: SortDirection;
	sort: SortState;
	onSort: (key: SortKey, first: SortDirection) => void;
}) {
	const active = sort?.key === sortKey ? sort.direction : null;
	return (
		<Button
			variant="ghost"
			size="sm"
			aria-label={t.traffic.servers.sortBy(label)}
			onPress={() => onSort(sortKey, first)}
			className="h-auto min-h-0 gap-1 rounded px-1 py-0.5 font-semibold"
		>
			<span className="max-w-24 whitespace-normal text-start leading-tight">{label}</span>
			<span aria-hidden className={active ? "text-accent" : "text-muted opacity-50"}>
				{active === "asc" ? "▲" : active === "desc" ? "▼" : "↕"}
			</span>
		</Button>
	);
}
