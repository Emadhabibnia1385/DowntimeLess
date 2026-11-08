import { Notice, PageHeader, SkeletonRows } from "@nyxon/nasim";
import { useEffect, useMemo, useState } from "react";
import { Loadable } from "@/shared/Loadable";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { whereOf } from "@/features/servers";
import { formatDate, formatNumber, t } from "@/strings";
import { useSeries, useSummary } from "../api";
import { serverLabel } from "../lib/rows";
import { dayStart, type Period, periodDays, periodWindow } from "../lib/period";
import { HourCard } from "./HourCard";
import { PeriodBar } from "./PeriodBar";
import { ServerTable } from "./ServerTable";
import { TopDaysCard } from "./TopDaysCard";
import { TrafficChartCard } from "./TrafficChartCard";
import { TrafficTiles } from "./TrafficTiles";

const TICK_MS = 60_000;
const nowSeconds = () => Math.floor(Date.now() / 1000);

// The clock the period is resolved against, so "today" rolls over while the page stays open.
function useNowSeconds(): number {
	const [now, setNow] = useState(nowSeconds);
	useEffect(() => {
		const timer = window.setInterval(() => setNow(nowSeconds()), TICK_MS);
		return () => window.clearInterval(timer);
	}, []);
	return now;
}

function rangeLine(period: Period, now: number): string | null {
	const days = periodDays(period, now);
	if (!days) return null;
	const zone = "Asia/Tehran";
	const count = days[1] - days[0];
	const first = formatDate(dayStart(days[0]), zone);
	return count === 1
		? t.traffic.rangeOne(first)
		: t.traffic.rangeMany(first, formatDate(dayStart(days[1] - 1), zone), formatNumber(count));
}

export function TrafficPage({
	period,
	serverId,
	onPeriodChange,
	onServerChange,
}: {
	period: Period;
	serverId: number | null;
	onPeriodChange: (period: Period) => void;
	onServerChange: (serverId: number | null) => void;
}) {
	useDocumentTitle(t.traffic.title);
	const now = useNowSeconds();
	const bounds = useMemo(() => periodWindow(period, now), [period, now]);
	const since = bounds?.since;
	const until = bounds?.until;
	const stable = useMemo(
		() => (since === undefined || until === undefined ? null : { since, until }),
		[since, until],
	);
	const summary = useSummary(stable);
	const series = useSeries(stable, serverId);
	const servers = useMemo(
		() =>
			(summary.data?.servers ?? []).map((server) => ({
				value: String(server.server_id),
				label:
					`${whereOf({ role: server.role, country: server.country }).flag} ${serverLabel(server)}`.trim(),
			})),
		[summary.data],
	);
	const picked =
		serverId === null ? undefined : summary.data?.servers.find((s) => s.server_id === serverId);
	const line = rangeLine(period, now);
	return (
		<div className="flex flex-col gap-6">
			<PageHeader title={t.traffic.title} description={t.traffic.subtitle} />
			<PeriodBar
				period={period}
				onPeriodChange={onPeriodChange}
				serverId={serverId}
				onServerChange={onServerChange}
				servers={servers}
				nowSeconds={now}
			/>
			{stable === null ? (
				<Notice tone="warning">{t.traffic.invalidRange}</Notice>
			) : (
				<>
					{line ? <p className="text-sm text-muted">{line}</p> : null}
					<Loadable query={summary} skeleton={<SkeletonRows rows={2} />}>
						{(data) => <TrafficTiles scope={picked ?? data.fleet} />}
					</Loadable>
					<Loadable query={series} skeleton={<SkeletonRows rows={3} />}>
						{(data) => (
							<>
								<TrafficChartCard data={data} fileName={`traffic-${serverId ?? "fleet"}`} />
								<div className="grid items-start gap-6 lg:grid-cols-2">
									<HourCard profile={data.hour_profile} />
									<TopDaysCard days={data.top_days} />
								</div>
							</>
						)}
					</Loadable>
					<ServerTable
						rows={summary.data?.servers}
						status={summary.isPending ? "loading" : summary.isError ? "error" : "ready"}
						onRetry={() => void summary.refetch()}
					/>
				</>
			)}
		</div>
	);
}
