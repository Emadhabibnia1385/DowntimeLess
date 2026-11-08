import { SectionCard, Spinner } from "@nyxon/nasim";
import { useState } from "react";
import type { FleetPoint } from "@/api/generated/model";
import { CHIP_RANGES, RANGES, type Range } from "@/features/servers";
import { LineChart } from "@/shared/charts/LineChart";
import { Loadable } from "@/shared/Loadable";
import { Segmented } from "@/shared/ui/Segmented";
import { t } from "@/strings";
import { useFleetHistory } from "../api";
import { buildFleet, TABS, type TabId } from "../lib/fleet";

const rangeOptions = CHIP_RANGES.map((value) => ({ value, label: t.server.ranges[value] }));
const tabOptions = TABS.map((value) => ({ value, label: t.dashboard.tabs[value] }));

function Charts({ tab, range, data }: { tab: TabId; range: Range; data: readonly FleetPoint[] }) {
	const fleet = buildFleet(tab, data, range);
	const wide = fleet.charts.length > 1;
	return (
		<div className="flex flex-col gap-4">
			<p className="text-sm text-muted">{fleet.description}</p>
			<div className={wide ? "grid gap-6 xl:grid-cols-2" : undefined}>
				{fleet.charts.map((chart) => (
					<LineChart
						key={`${tab}-${chart.key}`}
						title={chart.title}
						hideTitle={chart.hideTitle}
						times={fleet.times}
						series={chart.series}
						format={chart.format}
						axisFormat={chart.axisFormat}
						domain={chart.domain}
						unit={chart.unit}
						spanSeconds={RANGES[range]}
						fileName={`fleet-${chart.key}-${range}`}
						height={wide ? 280 : 320}
					/>
				))}
			</div>
		</div>
	);
}

// The whole fleet over a range (kept in the address): traffic, average usage and servers reporting.
export function FleetHistoryCard({
	range,
	onRangeChange,
}: {
	range: Range;
	onRangeChange: (range: Range) => void;
}) {
	const [tab, setTab] = useState<TabId>("traffic");
	const history = useFleetHistory(range);
	return (
		<SectionCard title={t.dashboard.history.title} description={t.dashboard.history.subtitle}>
			<div className="flex flex-col gap-5">
				<div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
					<Segmented
						label={t.server.range}
						value={range}
						onChange={onRangeChange}
						options={rangeOptions}
						className="sm:w-80"
					/>
					<Segmented
						label={t.dashboard.history.tabsLabel}
						value={tab}
						onChange={setTab}
						options={tabOptions}
						className="sm:w-96"
					/>
				</div>
				<Loadable query={history} skeleton={<Spinner />}>
					{(data) => <Charts tab={tab} range={range} data={data.points} />}
				</Loadable>
			</div>
		</SectionCard>
	);
}
