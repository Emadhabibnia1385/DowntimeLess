import { createFileRoute, redirect } from "@tanstack/react-router";

// The reports page moved into the issues page; an old bookmark lands on the matching tab.
export const Route = createFileRoute("/_app/reports")({
	validateSearch: (search: Record<string, unknown>): { tab?: "changes" } => ({
		tab: search.tab === "changes" ? "changes" : undefined,
	}),
	beforeLoad: ({ search }) => {
		throw redirect({
			to: "/issues",
			search: { tab: search.tab === "changes" ? "changes" : "health" },
			replace: true,
		});
	},
});
