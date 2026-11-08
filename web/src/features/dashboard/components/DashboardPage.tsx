import { PageHeader } from "@nyxon/nasim";
import type { Range } from "@/features/servers";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { FleetHistoryCard } from "./FleetHistoryCard";
import { IssuesCard } from "./IssuesCard";
import { PingCard } from "./PingCard";
import { RecurringCard } from "./RecurringCard";
import { SslCard } from "./SslCard";
import { StatTiles } from "./StatTiles";
import { TopServersCard } from "./TopServersCard";

// The fleet at a glance: key figures, one big history chart, then tables side by side.
export function DashboardPage({
	range,
	onRangeChange,
}: {
	range: Range;
	onRangeChange: (range: Range) => void;
}) {
	useDocumentTitle(t.dashboard.title);
	return (
		<div className="flex flex-col gap-5">
			<PageHeader title={t.dashboard.title} description={t.dashboard.subtitle} />
			<StatTiles range={range} />
			<FleetHistoryCard range={range} onRangeChange={onRangeChange} />
			<div className="grid gap-5 xl:grid-cols-2">
				<TopServersCard />
				<IssuesCard />
				<RecurringCard />
				<SslCard />
				<PingCard />
			</div>
		</div>
	);
}
