import { PageHeader, Tabs } from "@nyxon/nasim";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { isReportsTab, type ReportsTab } from "../lib/tabs";
import { BriefingTab } from "./BriefingTab";
import { ChangesTab } from "./ChangesTab";
import { HealthTab } from "./HealthTab";
import { PlaybooksTab } from "./PlaybooksTab";

export function ReportsPage({
	tab,
	onTabChange,
}: {
	tab: ReportsTab;
	onTabChange: (tab: ReportsTab) => void;
}) {
	useDocumentTitle(t.reports.title);
	return (
		<div className="flex flex-col gap-6">
			<PageHeader title={t.reports.title} description={t.reports.subtitle} />
			<Tabs
				label={t.reports.tabsLabel}
				selectedKey={tab}
				onSelectionChange={(id) => isReportsTab(id) && onTabChange(id)}
				items={[
					{ id: "ai", label: t.reports.tabs.ai, content: <BriefingTab /> },
					{ id: "health", label: t.reports.tabs.health, content: <HealthTab /> },
					{ id: "changes", label: t.reports.tabs.changes, content: <ChangesTab /> },
					{ id: "playbooks", label: t.reports.tabs.playbooks, content: <PlaybooksTab /> },
				]}
			/>
		</div>
	);
}
