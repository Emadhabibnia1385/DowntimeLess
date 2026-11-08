import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { DashboardPage, DEFAULT_RANGE, isDashRange } from "@/features/dashboard";
import type { Range } from "@/features/servers";

export const Route = createFileRoute("/_app/")({
	// The chart range lives in the address so a reload or a shared link keeps it.
	validateSearch: (search: Record<string, unknown>): { range?: Range } => ({
		range: isDashRange(search.range) ? search.range : undefined,
	}),
	component: DashboardRoute,
});

function DashboardRoute() {
	const { range } = Route.useSearch();
	const navigate = useNavigate({ from: Route.fullPath });
	return (
		<DashboardPage
			range={range ?? DEFAULT_RANGE}
			onRangeChange={(next) => void navigate({ search: { range: next }, replace: true })}
		/>
	);
}
