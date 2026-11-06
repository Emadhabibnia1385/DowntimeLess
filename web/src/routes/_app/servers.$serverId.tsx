import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { isRange, type Range, ServerDetailPage } from "@/features/servers";

export const Route = createFileRoute("/_app/servers/$serverId")({
	// The chart range lives in the address so a reload or a shared link keeps it.
	validateSearch: (search: Record<string, unknown>): { range?: Range } => ({
		range: isRange(search.range) ? search.range : undefined,
	}),
	component: ServerRoute,
});

function ServerRoute() {
	const { serverId } = Route.useParams();
	const { range } = Route.useSearch();
	const navigate = useNavigate({ from: Route.fullPath });
	return (
		<ServerDetailPage
			serverId={Number(serverId)}
			range={range ?? "24h"}
			onRangeChange={(next) => void navigate({ search: { range: next }, replace: true })}
		/>
	);
}
