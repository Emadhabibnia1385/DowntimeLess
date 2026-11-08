import { Skeleton, StatCard } from "@nyxon/nasim";
import type { ReactNode } from "react";
import { ArrowDownIcon, ArrowUpIcon } from "@/shared/icons";
import { useIssues } from "@/features/issues";
import { rankLinks, type Thresholds, usePingMatrix } from "@/features/ping-matrix";
import { useThresholds } from "@/features/settings";
import { type Range, useServers } from "@/features/servers";
import { summarize, useSsl } from "@/features/ssl";
import { formatBytes, formatNumber, formatPercent, t } from "@/strings";
import { useFleetHistory, useOverview, useTodayTraffic } from "../api";
import { fleetAverages, issueCounts } from "../lib/stats";

// Compact type so eight tiles fit one row beside the sidebar.
const TILE =
	"gap-1 p-3 sm:p-3 [&>div:first-child>p]:text-xs [&>div:nth-child(2)]:text-xl [&>p]:text-[11px] [&>p]:leading-5";
const COPY = t.dashboard.tiles;

type Shown = { value: string; hint?: string };
type Source<T> = { data: T | undefined; isPending: boolean };

// A tile waits with a bar where the figure goes, and shows a dash when its request failed.
function Tile<T>({
	label,
	source,
	icon,
	show,
}: {
	label: string;
	source: Source<T>;
	icon?: ReactNode;
	show: (data: T) => Shown;
}) {
	const { data, isPending } = source;
	const shown = data === undefined ? { value: t.common.none } : show(data);
	return (
		<StatCard
			className={TILE}
			label={label}
			icon={icon}
			value={isPending ? <Skeleton aria-hidden className="h-8 w-16 rounded-md" /> : shown.value}
			hint={isPending ? undefined : shown.hint}
		/>
	);
}

// A size split into number and unit, so the unit can sit in the hint and the tile stays narrow.
function sized(bytes: number): { value: string; unit: string } {
	const [value, ...unit] = formatBytes(bytes).split(" ");
	return { value, unit: unit.join(" ") };
}

const percentOrNone = (value: number | null) =>
	value === null ? t.common.none : formatPercent(value);

// Eight figures: servers, issues, traffic today and in the range, SSL, CPU, RAM, worst link.
export function StatTiles({ range }: { range: Range }) {
	const overview = useOverview();
	const fleet = useFleetHistory(range);
	const today = useTodayTraffic();
	const issues = useIssues();
	const certs = useSsl();
	const servers = useServers();
	const pings = usePingMatrix();
	const limits = useThresholds() as Thresholds;
	const rangeLabel = COPY.inRange(t.server.ranges[range]);
	const rangeTraffic = (data: { rx_total: number; tx_total: number }) => {
		const { value, unit } = sized(data.rx_total + data.tx_total);
		return {
			value,
			hint: `${unit} · ${COPY.split(formatBytes(data.rx_total), formatBytes(data.tx_total))} · ${rangeLabel}`,
		};
	};
	const todayTraffic = (data: {
		fleet: { today: { total: number }; yesterday: { total: number } };
	}) => {
		const { value, unit } = sized(data.fleet.today.total);
		return { value, hint: `${unit} · ${COPY.yesterday(formatBytes(data.fleet.yesterday.total))}` };
	};
	return (
		<section
			aria-label={t.dashboard.statsLabel}
			className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8 xl:gap-2"
		>
			<Tile
				label={COPY.servers}
				source={overview}
				show={(data) => ({
					value: COPY.serversValue(formatNumber(data.online), formatNumber(data.servers_total)),
					hint:
						data.pending > 0
							? COPY.serversPending(formatNumber(data.offline), formatNumber(data.pending))
							: COPY.serversHint(formatNumber(data.offline)),
				})}
			/>
			<Tile
				label={COPY.issues}
				source={issues}
				show={(data) => {
					const counts = issueCounts(data);
					return {
						value: formatNumber(counts.total),
						hint:
							counts.total === 0
								? COPY.issuesNone
								: COPY.issuesHint(
										formatNumber(counts.critical),
										formatNumber(counts.warning),
										formatNumber(counts.info),
									),
					};
				}}
			/>
			<Tile label={COPY.trafficToday} source={today} icon={<ArrowDownIcon />} show={todayTraffic} />
			<Tile label={COPY.trafficRange} source={fleet} icon={<ArrowUpIcon />} show={rangeTraffic} />
			<Tile
				label={COPY.ssl}
				source={certs}
				show={(rows) => {
					const counts = summarize(rows);
					return {
						value: formatNumber(counts.critical + counts.expiring),
						hint:
							counts.total === 0
								? COPY.sslNone
								: COPY.sslHint(formatNumber(counts.critical), formatNumber(counts.total)),
					};
				}}
			/>
			<Tile
				label={COPY.cpu}
				source={servers}
				show={(rows) => {
					const average = fleetAverages(rows);
					return {
						value: percentOrNone(average.cpu),
						hint:
							average.cpuCount === 0
								? COPY.noOnline
								: COPY.onServers(formatNumber(average.cpuCount)),
					};
				}}
			/>
			<Tile
				label={COPY.ram}
				source={servers}
				show={(rows) => {
					const average = fleetAverages(rows);
					return {
						value: percentOrNone(average.ram),
						hint:
							average.ramCount === 0
								? COPY.noOnline
								: COPY.onServers(formatNumber(average.ramCount)),
					};
				}}
			/>
			<Tile
				label={COPY.ping}
				source={pings}
				show={(cells) => {
					const worst = rankLinks(cells, limits)[0];
					if (!worst) return { value: t.common.none, hint: COPY.pingNone };
					return {
						value: percentOrNone(worst.loss),
						hint: COPY.pingHint(worst.cell.from_name, worst.cell.to_name),
					};
				}}
			/>
		</section>
	);
}
