import { PageHeader, Tabs } from "@nyxon/nasim";
import { Loadable } from "@/shared/Loadable";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { useIssues } from "../api";
import { type HistoryRange, type IssuesFilters, type IssuesTab, isIssuesTab } from "../lib/tabs";
import { ChangesTab } from "./ChangesTab";
import { HealthTab } from "./HealthTab";
import { IssueHistory } from "./IssueHistory";
import { IssueTable } from "./IssueTable";

function NowTab() {
	const issues = useIssues();
	return <Loadable query={issues}>{(items) => <IssueTable issues={items} />}</Loadable>;
}

export function IssuesPage({
	tab,
	range,
	onTabChange,
	onRangeChange,
	filters,
	onFiltersChange,
}: {
	tab: IssuesTab;
	range: HistoryRange;
	onTabChange: (tab: IssuesTab) => void;
	onRangeChange: (range: HistoryRange) => void;
	filters: IssuesFilters;
	onFiltersChange: (filters: IssuesFilters) => void;
}) {
	useDocumentTitle(t.issues.title);
	return (
		<div className="flex flex-col gap-6">
			<PageHeader title={t.issues.title} description={t.issues.subtitle} />
			<Tabs
				label={t.issueHistory.tabsLabel}
				selectedKey={tab}
				onSelectionChange={(id) => isIssuesTab(id) && onTabChange(id)}
				items={[
					{ id: "now", label: t.issueHistory.tabNow, content: <NowTab /> },
					{
						id: "history",
						label: t.issueHistory.tabHistory,
						content: <IssueHistory range={range} onRangeChange={onRangeChange} />,
					},
					{
						id: "health",
						label: t.issueHealth.title,
						content: (
							<HealthTab
								band={filters.band}
								onBandChange={(band) => onFiltersChange({ ...filters, band })}
							/>
						),
					},
					{
						id: "changes",
						label: t.issueChanges.title,
						content: (
							<ChangesTab
								period={filters.period}
								kind={filters.kind}
								onPeriodChange={(period) => onFiltersChange({ ...filters, period })}
								onKindChange={(kind) => onFiltersChange({ ...filters, kind })}
							/>
						),
					},
				]}
			/>
		</div>
	);
}
