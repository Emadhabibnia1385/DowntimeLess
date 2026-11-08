import { SectionCard, Spinner } from "@nyxon/nasim";
import { useState } from "react";
import { useServersMetrics } from "@/api/generated/servers/servers";
import { Loadable } from "@/shared/Loadable";
import { Segmented } from "@/shared/ui/Segmented";
import { t } from "@/strings";
import { CHIP_RANGES, RANGES, type Range } from "../lib/chart";
import { TABS, type TabId } from "../lib/history";
import { HistoryCharts } from "./HistoryCharts";

const rangeOptions = CHIP_RANGES.map((value) => ({ value, label: t.server.ranges[value] }));
const tabOptions = TABS.map((value) => ({ value, label: t.history.tabs[value] }));

// CPU, memory, network, load and connections over a range (kept in the address) as line charts.
export function HistoryCard({
	serverId,
	range,
	onRangeChange,
	cores,
}: {
	serverId: number;
	range: Range;
	onRangeChange: (range: Range) => void;
	cores?: number | null;
}) {
	const [tab, setTab] = useState<TabId>("usage");
	const metrics = useServersMetrics(serverId, { range }, { query: { refetchInterval: 60_000 } });
	return (
		<SectionCard title={t.history.title} description={t.history.subtitle}>
			<div className="flex flex-col gap-5">
				<div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
					<Segmented
						label={t.server.range}
						value={range}
						onChange={onRangeChange}
						options={rangeOptions}
						className="xl:w-80"
					/>
					<Segmented
						label={t.history.tabsLabel}
						value={tab}
						onChange={setTab}
						options={tabOptions}
						className="xl:min-w-0 xl:flex-1 xl:max-w-xl"
					/>
				</div>
				<Loadable query={metrics} skeleton={<Spinner />}>
					{(data) => (
						<HistoryCharts
							serverId={serverId}
							tab={tab}
							range={range}
							spanSeconds={RANGES[range]}
							points={data.points}
							cores={cores}
						/>
					)}
				</Loadable>
			</div>
		</SectionCard>
	);
}
