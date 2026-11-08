import { Button } from "@nyxon/nasim";
import { t } from "@/strings";
import type { SortKey, SortState } from "../lib/health";

export function SortButton({
	label,
	sortKey,
	sort,
	onSort,
}: {
	label: string;
	sortKey: SortKey;
	sort: SortState;
	onSort: (key: SortKey) => void;
}) {
	const active = sort?.key === sortKey ? sort.direction : null;
	return (
		<Button
			variant="ghost"
			size="sm"
			aria-label={t.reports.health.sortBy(label)}
			onPress={() => onSort(sortKey)}
			className="h-auto min-h-0 gap-1 rounded px-1 py-0.5 text-xs font-medium text-inherit"
		>
			{label}
			<span aria-hidden className={active ? "text-accent" : "text-muted opacity-50"}>
				{active === "asc" ? "▲" : active === "desc" ? "▼" : "↕"}
			</span>
		</Button>
	);
}
