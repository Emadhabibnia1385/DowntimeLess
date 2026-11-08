import type { FleetPoint } from "@/api/generated/model";
import type { ChartSeries } from "@/shared/charts/types";
import { formatBytes, formatDecimal, formatNumber, formatPercent, t } from "@/strings";

export const TABS = ["traffic", "usage", "servers"] as const;
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

export type Fleet = { times: number[]; description: string; charts: ChartSpec[] };

/** Seconds one point covers, as the master buckets each range. */
const BUCKET_S: Record<string, number> = {
	"1h": 30,
	"6h": 60,
	"24h": 300,
	"7d": 1800,
	"30d": 7200,
};
const DEFAULT_BUCKET_S = 300;
const MEGA = 1_000_000;
const BITS = 8;

const names = t.dashboard.series;
const mbps = (value: number) => `${formatDecimal(value, value < 10 ? 2 : 1)} ${t.units.megabit}`;
const decimal = (value: number) => formatDecimal(value, 2);
const percent = { format: formatPercent, axisFormat: formatPercent } as const;

type Pick = (point: FleetPoint) => number | null | undefined;

// A series nobody reported has no line and no chip.
function lines(
	points: readonly FleetPoint[],
	specs: readonly [
		key: string,
		label: string,
		tone: ChartSeries["tone"],
		pick: Pick,
		area?: boolean,
	][],
): ChartSeries[] {
	return specs.flatMap(([key, label, tone, pick, area]) => {
		const values = points.map((point) => pick(point) ?? null);
		return values.some((value) => value !== null) ? [{ key, label, tone, values, area }] : [];
	});
}

type Build = (points: readonly FleetPoint[], bucketSeconds: number) => Omit<Fleet, "times">;

const traffic: Build = (points, bucket) => {
	const speed =
		(pick: Pick): Pick =>
		(point) => {
			const bytes = pick(point);
			return bytes == null ? null : (bytes * BITS) / bucket / MEGA;
		};
	return {
		description: t.dashboard.trafficHint,
		charts: [
			{
				key: "speed",
				title: t.dashboard.speedTitle,
				hideTitle: false,
				format: mbps,
				axisFormat: decimal,
				unit: t.units.megabit,
				series: lines(points, [
					["rx", names.rx, "accent", speed((p) => p.rx_bytes), true],
					["tx", names.tx, "info", speed((p) => p.tx_bytes), true],
				]),
			},
			{
				key: "volume",
				title: t.dashboard.volumeTitle,
				hideTitle: false,
				format: formatBytes,
				series: lines(points, [
					["rx", names.rx, "accent", (p) => p.rx_bytes, true],
					["tx", names.tx, "info", (p) => p.tx_bytes, true],
				]),
			},
		],
	};
};

const usage: Build = (points) => ({
	description: t.dashboard.usageHint,
	charts: [
		{
			key: "usage",
			title: t.dashboard.tabs.usage,
			hideTitle: true,
			domain: [0, 100] as const,
			...percent,
			series: lines(points, [
				["cpu", names.cpu, "accent", (p) => p.cpu, true],
				["ram", names.ram, "info", (p) => p.ram_pct],
				["disk", names.disk, "warning", (p) => p.disk_pct],
			]),
		},
	],
});

const servers: Build = (points) => ({
	description: t.dashboard.serversHint,
	charts: [
		{
			key: "servers",
			title: t.dashboard.tabs.servers,
			hideTitle: true,
			format: formatNumber,
			series: lines(points, [["servers", names.servers, "accent", (p) => p.servers, true]]),
		},
	],
});

const BUILDERS: Record<TabId, Build> = { traffic, usage, servers };

/** The tab's charts from the fleet points, oldest first. */
export function buildFleet(tab: TabId, input: readonly FleetPoint[], range: string): Fleet {
	const points = [...input].sort((a, b) => a.ts - b.ts);
	return {
		times: points.map((point) => point.ts),
		...BUILDERS[tab](points, BUCKET_S[range] ?? DEFAULT_BUCKET_S),
	};
}
