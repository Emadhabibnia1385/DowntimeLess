import { PageHeader } from "@nyxon/nasim";
import { Loadable } from "@/shared/Loadable";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { useIssues } from "../api";
import { IssueList } from "./IssueList";

export function IssuesPage() {
	useDocumentTitle(t.issues.title);
	const issues = useIssues();
	return (
		<div className="flex flex-col gap-6">
			<PageHeader title={t.issues.title} description={t.issues.subtitle} />
			<Loadable query={issues}>{(items) => <IssueList issues={items} />}</Loadable>
		</div>
	);
}
