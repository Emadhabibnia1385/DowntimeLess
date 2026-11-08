import { PageHeader, Tabs } from "@nyxon/nasim";
import { Loadable } from "@/shared/Loadable";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { useIssues } from "../api";
import { type HistoryRange, type IssuesTab, isIssuesTab } from "../lib/tabs";
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
}: {
	tab: IssuesTab;
	range: HistoryRange;
	onTabChange: (tab: IssuesTab) => void;
	onRangeChange: (range: HistoryRange) => void;
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
				]}
			/>
		</div>
	);
}
