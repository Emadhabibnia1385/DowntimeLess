import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { isPeriodId, type Period, type PeriodId, parseDay, TrafficPage } from "@/features/traffic";

type TrafficSearch = { period?: PeriodId; from?: string; to?: string; server?: number };

export const Route = createFileRoute("/_app/traffic")({
	// The period, a custom range and the server live in the address so a reload or a link keeps them.
	validateSearch: (search: Record<string, unknown>): TrafficSearch => {
		const server = Number(search.server);
		const period = isPeriodId(search.period) ? search.period : undefined;
		const day = (value: unknown) =>
			typeof value === "string" && parseDay(value) !== null ? value : undefined;
		return {
			period,
			from: period === "custom" ? day(search.from) : undefined,
			to: period === "custom" ? day(search.to) : undefined,
			server: Number.isInteger(server) && server > 0 ? server : undefined,
		};
	},
	component: TrafficRoute,
});

function TrafficRoute() {
	const { period, from, to, server } = Route.useSearch();
	const navigate = useNavigate({ from: Route.fullPath });
	const current: Period = { id: period ?? "30d", from, to };
	return (
		<TrafficPage
			period={current}
			serverId={server ?? null}
			onPeriodChange={(next) =>
				void navigate({
					search: (prev) => ({
						...prev,
						period: next.id === "30d" ? undefined : next.id,
						from: next.from,
						to: next.to,
					}),
					replace: true,
				})
			}
			onServerChange={(next) =>
				void navigate({ search: (prev) => ({ ...prev, server: next ?? undefined }), replace: true })
			}
		/>
	);
}
