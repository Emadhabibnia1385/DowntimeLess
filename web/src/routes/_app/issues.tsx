import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
	DEFAULT_FILTERS,
	filtersToSearch,
	type HistoryRange,
	isBand,
	isEventKind,
	isHistoryRange,
	isIssuesTab,
	isPeriod,
	type IssuesTab,
	IssuesPage,
} from "@/features/issues";

type Filters = ReturnType<typeof filtersToSearch>;

export const Route = createFileRoute("/_app/issues")({
	// Tab, range and filters live in the address so a reload or a shared link keeps them.
	validateSearch: (
		search: Record<string, unknown>,
	): { tab?: Exclude<IssuesTab, "now">; range?: HistoryRange } & Filters => ({
		tab: isIssuesTab(search.tab) && search.tab !== "now" ? search.tab : undefined,
		range: isHistoryRange(search.range) ? search.range : undefined,
		period: isPeriod(search.period) ? search.period : undefined,
		kind: isEventKind(search.kind) ? search.kind : undefined,
		band: isBand(search.band) ? search.band : undefined,
	}),
	component: IssuesRoute,
});

function IssuesRoute() {
	const { tab, range, period, kind, band } = Route.useSearch();
	const navigate = useNavigate({ from: Route.fullPath });
	return (
		<IssuesPage
			tab={tab ?? "now"}
			range={range ?? "24h"}
			filters={{
				period: period ?? DEFAULT_FILTERS.period,
				kind: kind ?? DEFAULT_FILTERS.kind,
				band: band ?? DEFAULT_FILTERS.band,
			}}
			onTabChange={(next) =>
				void navigate({
					search: (prev) => ({ ...prev, tab: next === "now" ? undefined : next }),
					replace: true,
				})
			}
			onRangeChange={(next) =>
				void navigate({ search: (prev) => ({ ...prev, range: next }), replace: true })
			}
			onFiltersChange={(next) =>
				void navigate({
					search: (prev) => ({ ...prev, ...filtersToSearch(next) }),
					replace: true,
				})
			}
		/>
	);
}
