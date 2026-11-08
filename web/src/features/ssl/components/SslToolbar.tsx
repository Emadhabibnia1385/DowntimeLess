import { FilterChips, SearchBox } from "@nyxon/nasim";
import { t } from "@/strings";
import type { StatusFilter } from "../lib/view";

const OPTIONS: { value: StatusFilter; label: string }[] = [
	{ value: "all", label: t.ssl.filterAll },
	{ value: "critical", label: t.ssl.filterCritical },
	{ value: "warning", label: t.ssl.filterWarning },
	{ value: "ok", label: t.ssl.filterOk },
];

// Show only one state of certificate, or only what matches the typed text.
export function SslToolbar({
	status,
	onStatus,
	query,
	onQuery,
}: {
	status: StatusFilter;
	onStatus: (value: StatusFilter) => void;
	query: string;
	onQuery: (value: string) => void;
}) {
	return (
		<div className="flex flex-wrap items-start justify-between gap-3">
			<FilterChips
				label={t.ssl.filterStatus}
				value={status}
				onChange={(value) => onStatus(value as StatusFilter)}
				options={OPTIONS}
			/>
			<SearchBox
				label={t.ssl.search}
				placeholder={t.ssl.searchPlaceholder}
				value={query}
				onChange={onQuery}
			/>
		</div>
	);
}
