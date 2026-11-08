import { EmptyState, SelectField, StaticTable } from "@nyxon/nasim";
import { useState } from "react";
import type { ServerOut } from "@/api/generated/model";
import { ServerLabel } from "@/features/issues";
import { displayName, useServers } from "@/features/servers";
import { flagOf, formatDecimal, formatPercent, t } from "@/strings";
import { type SortBy, topServers } from "../lib/stats";
import { COMPACT_TABLE, DataCard } from "./DataCard";

const COPY = t.dashboard.top;
const SHOWN = 8;
const MEGA = 1_000_000;
const HOT = 90;
const WARM = 75;
const sortOptions = [
	{ value: "cpu", label: COPY.byCpu },
	{ value: "traffic", label: COPY.byTraffic },
];

function Level({ value }: { value: number | null | undefined }) {
	if (value == null) return t.common.none;
	const tone = value >= HOT ? "text-danger" : value >= WARM ? "text-warning" : "";
	return <span className={`tabular-nums ${tone}`}>{formatPercent(value)}</span>;
}

// The agent reports network rates in bits per second.
function Speed({ bps }: { bps: number | null | undefined }) {
	if (bps == null) return t.common.none;
	return <span className="tabular-nums">{formatDecimal(bps / MEGA, bps < 10 * MEGA ? 2 : 1)}</span>;
}

function rowOf(server: ServerOut) {
	const { latest } = server;
	return {
		id: String(server.id),
		cells: [
			<ServerLabel
				key="name"
				serverId={server.id}
				name={displayName(server)}
				flag={flagOf(server.country)}
			/>,
			<Level key="cpu" value={latest.cpu_pct} />,
			<Level key="ram" value={latest.ram_pct} />,
			<Level key="disk" value={latest.disk_pct} />,
			<Speed key="rx" bps={latest.rx_bps} />,
			<Speed key="tx" bps={latest.tx_bps} />,
		],
	};
}

// The busiest online servers by CPU or by traffic, with the figures the server page leads with.
export function TopServersCard() {
	const servers = useServers();
	const [by, setBy] = useState<SortBy>("cpu");
	return (
		<DataCard
			title={COPY.title}
			description={COPY.subtitle}
			href="/servers"
			linkLabel={COPY.all}
			query={servers}
		>
			{(rows) => {
				const top = topServers(rows, by, SHOWN);
				if (top.length === 0) {
					return (
						<EmptyState
							title={COPY.emptyTitle}
							description={COPY.empty}
							action={{ label: COPY.add, href: "/servers" }}
						/>
					);
				}
				return (
					<div className="flex flex-col gap-3">
						<SelectField
							label={COPY.sortLabel}
							value={by}
							onChange={(next) => setBy(next === "traffic" ? "traffic" : "cpu")}
							options={sortOptions}
							className="w-44"
						/>
						<StaticTable
							caption={COPY.tableLabel}
							className={COMPACT_TABLE}
							columns={[COPY.server, COPY.cpu, COPY.ram, COPY.disk, COPY.rx, COPY.tx]}
							rows={top.map(rowOf)}
						/>
					</div>
				);
			}}
		</DataCard>
	);
}
