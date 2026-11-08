import { EmptyState, StaticTable } from "@nyxon/nasim";
import {
	HealthChip,
	type RankedLink,
	rankLinks,
	type Thresholds,
	usePingMatrix,
} from "@/features/ping-matrix";
import { ServerLabel } from "@/features/issues";
import { useServers } from "@/features/servers";
import { useThresholds } from "@/features/settings";
import { flagOf, formatMs, formatPercent, t } from "@/strings";
import { COMPACT_TABLE, DataCard } from "./DataCard";

const COPY = t.dashboard.ping;
const SHOWN = 6;
const IRAN = flagOf("IR");

// The weakest Iran-to-abroad links: packet loss, round-trip time and the verdict on a chip.
export function PingCard() {
	const pings = usePingMatrix();
	const servers = useServers();
	const limits = useThresholds() as Thresholds;
	const countryOf = new Map((servers.data ?? []).map((server) => [server.id, server.country]));
	const row = ({ cell, loss, rtt, health }: RankedLink) => ({
		id: `${cell.from_id}-${String(cell.to_id)}`,
		cells: [
			<ServerLabel key="from" serverId={cell.from_id} name={cell.from_name} flag={IRAN} />,
			<ServerLabel
				key="to"
				serverId={typeof cell.to_id === "number" ? cell.to_id : null}
				name={cell.to_name}
				flag={typeof cell.to_id === "number" ? flagOf(countryOf.get(cell.to_id)) : ""}
			/>,
			<span key="loss" className="tabular-nums">
				{loss === null ? t.common.none : formatPercent(loss)}
			</span>,
			<span key="rtt" className="whitespace-nowrap tabular-nums">
				{rtt === null ? t.common.none : formatMs(rtt)}
			</span>,
			<HealthChip key="health" health={health} />,
		],
	});
	return (
		<DataCard
			title={COPY.title}
			description={COPY.subtitle}
			href="/ping-matrix"
			linkLabel={COPY.all}
			query={pings}
			className="xl:col-span-2"
		>
			{(cells) => {
				if (cells.length === 0) {
					return <EmptyState title={COPY.emptyTitle} description={COPY.empty} />;
				}
				return (
					<StaticTable
						caption={COPY.tableLabel}
						className={COMPACT_TABLE}
						columns={[COPY.from, COPY.to, COPY.loss, COPY.rtt, COPY.health]}
						rows={rankLinks(cells, limits).slice(0, SHOWN).map(row)}
					/>
				);
			}}
		</DataCard>
	);
}
