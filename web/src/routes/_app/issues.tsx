import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
	type HistoryRange,
	isHistoryRange,
	isIssuesTab,
	type IssuesTab,
	IssuesPage,
} from "@/features/issues";

export const Route = createFileRoute("/_app/issues")({
	// The open tab and the history range live in the address so a reload or a shared link keeps them.
	validateSearch: (
		search: Record<string, unknown>,
	): { tab?: Exclude<IssuesTab, "now">; range?: HistoryRange } => ({
		tab: isIssuesTab(search.tab) && search.tab !== "now" ? search.tab : undefined,
		range: isHistoryRange(search.range) ? search.range : undefined,
	}),
	component: IssuesRoute,
});

function IssuesRoute() {
	const { tab, range } = Route.useSearch();
	const navigate = useNavigate({ from: Route.fullPath });
	return (
		<IssuesPage
			tab={tab ?? "now"}
			range={range ?? "24h"}
			onTabChange={(next) =>
				void navigate({
					search: (prev) => ({ ...prev, tab: next === "now" ? undefined : next }),
					replace: true,
				})
			}
			onRangeChange={(next) =>
				void navigate({ search: (prev) => ({ ...prev, range: next }), replace: true })
			}
		/>
	);
}
