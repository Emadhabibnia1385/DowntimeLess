import { Button, Tooltip } from "@nyxon/nasim";
import { t } from "@/strings";
import type { SortDirection, SortKey, SortState } from "../lib/sort";

const TRIGGER = "h-auto min-h-0 gap-1 rounded px-1 py-0.5 font-semibold";
const TIP = "max-w-64 break-normal text-pretty text-start leading-relaxed";

// Sorts when pressed and explains the column on hover; the trigger must be a Nasim Button.
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
		<Tooltip>
			<Button
				variant="ghost"
				size="sm"
				aria-label={t.servers.sortBy(label)}
				onPress={() => onSort(sortKey, first)}
				className={TRIGGER}
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
			</Button>
			<Tooltip.Content className={TIP}>
				{t.servers.help[sortKey as keyof typeof t.servers.help]}
			</Tooltip.Content>
		</Tooltip>
	);
}

// The same explanation on a title that does not sort.
export function PlainHeader({ label, help }: { label: string; help: string }) {
	return (
		<Tooltip>
			<Button variant="ghost" size="sm" className={`${TRIGGER} cursor-help`}>
				{label}
			</Button>
			<Tooltip.Content className={TIP}>{help}</Tooltip.Content>
		</Tooltip>
	);
}
