import type { MetricPoint } from "@/api/generated/model";
import type { ChartSeries } from "@/shared/charts/types";
import { formatBytes, formatDecimal, formatNumber, formatPercent, t } from "@/strings";

export const TABS = ["usage", "network", "load", "quality", "conns"] as const;
export type TabId = (typeof TABS)[number];

export type ChartSpec = {
	key: string;
	title: string;
	hideTitle: boolean;
	series: ChartSeries[];
	format: (value: number) => string;
	axisFormat?: (value: number) => string;
	domain?: readonly [number, number];
	unit?: string;
};

export type History = { times: number[]; description: string; charts: ChartSpec[] };

type Context = { points: readonly MetricPoint[]; cores?: number | null };
type Pick = (point: MetricPoint) => number | null | undefined;
type Tone = ChartSeries["tone"];

const MEGA = 1_000_000;
const mbps = (value: number) => `${formatDecimal(value, value < 10 ? 2 : 1)} ${t.units.megabit}`;
const decimal = (value: number) => formatDecimal(value, 2);
const megabits = (value: number | null | undefined) => (value == null ? null : value / MEGA);
const names = t.history.series;

// A series the agent never reported has no line and no chip.
function lines(
	points: readonly MetricPoint[],
	specs: readonly [key: string, label: string, tone: Tone, pick: Pick, area?: boolean][],
): ChartSeries[] {
	return specs.flatMap(([key, label, tone, pick, area]) => {
		const values = points.map((point) => pick(point) ?? null);
		return values.some((value) => value !== null) ? [{ key, label, tone, values, area }] : [];
	});
}

const percent = { format: formatPercent, axisFormat: formatPercent } as const;

const usage = ({ points }: Context) => ({
	description: t.history.usageHint,
	charts: [
		{
			key: "usage",
			title: t.history.tabs.usage,
			hideTitle: true,
			domain: [0, 100] as const,
			...percent,
			series: lines(points, [
				["cpu", names.cpu, "accent", (p) => p.cpu, true],
				["ram", names.ram, "info", (p) => p.ram_pct],
				["disk", names.disk, "warning", (p) => p.disk_pct],
				["swap", names.swap, "muted", (p) => p.swap_pct],
			]),
		},
	],
});

const network = ({ points }: Context) => ({
	description: t.history.networkHint,
	charts: [
		{
			key: "speed",
			title: t.history.tabs.network,
			hideTitle: true,
			format: mbps,
			axisFormat: decimal,
			unit: t.units.megabit,
			series: lines(points, [
				["rx", names.rx, "accent", (p) => megabits(p.rx_bps), true],
				["tx", names.tx, "info", (p) => megabits(p.tx_bps), true],
			]),
		},
		{
			key: "volume",
			title: t.history.volumeTitle,
			hideTitle: false,
			format: formatBytes,
			series: lines(points, [
				["rx", names.rx, "accent", (p) => p.rx_bytes, true],
				["tx", names.tx, "info", (p) => p.tx_bytes, true],
			]),
		},
	],
});

const load = ({ points, cores }: Context) => ({
	description: `${t.history.loadHint}${cores ? ` ${t.history.loadCores(formatNumber(cores))}` : ""}`,
	charts: [
		{
			key: "load",
			title: t.history.tabs.load,
			hideTitle: true,
			format: decimal,
			series: lines(points, [["load1", names.load1, "accent", (p) => p.load1, true]]),
		},
	],
});

const quality = ({ points }: Context) => ({
	description: t.history.qualityHint,
	charts: [
		{
			key: "quality",
			title: t.history.tabs.quality,
			hideTitle: true,
			...percent,
			series: lines(points, [
				["steal", names.steal, "warning", (p) => p.steal],
				["retrans", names.retrans, "danger", (p) => p.retrans],
				["conntrack", names.conntrack, "info", (p) => p.conntrack],
			]),
		},
	],
});

const conns = ({ points }: Context) => ({
	description: t.history.connsHint,
	charts: [
		{
			key: "conns",
			title: t.history.tabs.conns,
			hideTitle: true,
			format: formatNumber,
			series: lines(points, [["conns", names.conns, "accent", (p) => p.conns, true]]),
		},
	],
});

const BUILDERS: Record<TabId, (context: Context) => Omit<History, "times">> = {
	usage,
	network,
	load,
	quality,
	conns,
};

/** The tab's charts from the metric points, oldest first. */
export function buildHistory(
	tab: TabId,
	input: readonly MetricPoint[],
	cores?: number | null,
): History {
	const points = [...input].sort((a, b) => a.ts - b.ts);
	return { times: points.map((point) => point.ts), ...BUILDERS[tab]({ points, cores }) };
}
