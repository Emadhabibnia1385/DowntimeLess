import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { isReportsTab, ReportsPage, type ReportsTab } from "@/features/reports";

export const Route = createFileRoute("/_app/reports")({
	// The open tab lives in the address so a reload or a shared link keeps it.
	validateSearch: (search: Record<string, unknown>): { tab?: Exclude<ReportsTab, "ai"> } => ({
		tab: isReportsTab(search.tab) && search.tab !== "ai" ? search.tab : undefined,
	}),
	component: ReportsRoute,
});

function ReportsRoute() {
	const { tab } = Route.useSearch();
	const navigate = useNavigate({ from: Route.fullPath });
	return (
		<ReportsPage
			tab={tab ?? "ai"}
			onTabChange={(next) =>
				void navigate({ search: { tab: next === "ai" ? undefined : next }, replace: true })
			}
		/>
	);
}
