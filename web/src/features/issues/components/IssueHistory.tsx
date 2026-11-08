import {
	EmptyState,
	FilterChips,
	SearchBox,
	SectionCard,
	SelectField,
	SkeletonRows,
	StatCard,
} from "@nyxon/nasim";
import { useMemo, useState } from "react";
import type { IssuesHistory } from "@/api/generated/model";
import { useServers } from "@/features/servers";
import { Loadable } from "@/shared/Loadable";
import { flagOf, formatNumber, t } from "@/strings";
import { useHistory } from "../api";
import { filterSummary, SEVERITY_FILTERS, type SortState, sortSummary } from "../lib/history";
import { HISTORY_RANGES, type HistoryRange } from "../lib/tabs";
import { HistorySummary } from "./HistorySummary";
import { IncidentTimeline } from "./IncidentTimeline";

const ALL = "all";
const SEVERITY_LABELS: Record<string, string> = t.severity;
const rangeOptions = HISTORY_RANGES.map((value) => ({
	value,
	label: t.issueHistory.ranges[value],
}));
const severityOptions = [
	{ value: ALL, label: t.issueHistory.severityAll },
	...SEVERITY_FILTERS.map((value) => ({ value, label: SEVERITY_LABELS[value] })),
];

function Stats({ totals }: { totals: IssuesHistory["totals"] }) {
	const h = t.issueHistory;
	return (
		<section aria-label={h.statsLabel} className="grid grid-cols-2 gap-3 md:grid-cols-4">
			<StatCard
				label={h.statOccurrences}
				value={formatNumber(totals.occurrences)}
				hint={h.statOccurrencesHint}
			/>
			<StatCard label={h.statIssues} value={formatNumber(totals.issues)} hint={h.statIssuesHint} />
			<StatCard
				label={h.statActive}
				value={formatNumber(totals.active_now)}
				hint={h.statActiveHint}
			/>
			<StatCard
				label={h.statCritical}
				value={formatNumber(totals.critical)}
				hint={h.statCriticalHint}
			/>
		</section>
	);
}

// What happened over 24 hours, 7 or 30 days, including problems that are gone by now.
export function IssueHistory({
	range,
	onRangeChange,
}: {
	range: HistoryRange;
	onRangeChange: (range: HistoryRange) => void;
}) {
	const history = useHistory(range);
	const servers = useServers();
	const [query, setQuery] = useState("");
	const [severity, setSeverity] = useState(ALL);
	const [sort, setSort] = useState<SortState>(null);
	const flags = useMemo(
		() => new Map((servers.data ?? []).map((server) => [server.id, flagOf(server.country)])),
		[servers.data],
	);
	return (
		<div className="flex flex-col gap-6">
			<FilterChips
				label={t.issueHistory.rangeLabel}
				value={range}
				onChange={(value) => onRangeChange(value as HistoryRange)}
				options={rangeOptions}
			/>
			<Loadable query={history} skeleton={<SkeletonRows />}>
				{(data) => {
					if (data.summary.length === 0) {
						return (
							<>
								<Stats totals={data.totals} />
								<EmptyState title={t.issueHistory.emptyTitle} description={t.issueHistory.empty} />
							</>
						);
					}
					const filtered = filterSummary(data.summary, { query, severity });
					return (
						<>
							<Stats totals={data.totals} />
							<SectionCard title={t.issueHistory.summaryTitle}>
								<div className="flex flex-col gap-4">
									<div className="grid max-w-xl items-end gap-3 sm:grid-cols-2">
										<SearchBox
											label={t.issueHistory.search}
											placeholder={t.issueHistory.searchPlaceholder}
											value={query}
											onChange={setQuery}
										/>
										<SelectField
											label={t.issueHistory.severityField}
											value={severity}
											onChange={(next) => setSeverity(next ?? ALL)}
											options={severityOptions}
										/>
									</div>
									<HistorySummary
										rows={sortSummary(filtered, sort)}
										flags={flags}
										sort={sort}
										onSort={setSort}
										filtered={data.summary.length > 0 && filtered.length === 0}
									/>
								</div>
							</SectionCard>
							<SectionCard title={t.issueHistory.timelineTitle}>
								<IncidentTimeline
									incidents={data.incidents}
									total={data.totals.occurrences}
									flags={flags}
								/>
							</SectionCard>
						</>
					);
				}}
			</Loadable>
		</div>
	);
}
