import { EmptyState, StaticTable, StatusChip } from "@nyxon/nasim";
import { Link } from "@tanstack/react-router";
import type { SslRow } from "@/api/generated/model";
import { certStatus, daysLeftLabel, useSsl } from "@/features/ssl";
import { t } from "@/strings";
import { nearestExpiry } from "../lib/stats";
import { COMPACT_TABLE, DataCard } from "./DataCard";

const COPY = t.dashboard.ssl;
const SHOWN = 6;

function Where({ row }: { row: SslRow }) {
	if (row.server_id === null) return <span className="whitespace-nowrap">{t.ssl.fromOutside}</span>;
	return (
		<Link
			to="/servers/$serverId"
			params={{ serverId: String(row.server_id) }}
			className="whitespace-nowrap text-accent-soft-foreground underline-offset-4 hover:underline"
		>
			{row.server_name ?? String(row.server_id)}
		</Link>
	);
}

// The chip says the days left, coloured by the certificate's level; a failed check says so instead.
function Left({ row }: { row: SslRow }) {
	const status = certStatus(row);
	const label = !row.error && row.days_left !== null ? daysLeftLabel(row.days_left) : status.label;
	return <StatusChip tone={status.tone} label={label} size="sm" />;
}

// The certificates that expire first, as a table with a way into the full list.
export function SslCard() {
	const certs = useSsl();
	return (
		<DataCard
			title={COPY.title}
			description={COPY.subtitle}
			href="/ssl"
			linkLabel={COPY.all}
			query={certs}
		>
			{(rows) => {
				if (rows.length === 0) {
					return <EmptyState title={COPY.emptyTitle} description={COPY.empty} />;
				}
				return (
					<StaticTable
						caption={COPY.tableLabel}
						className={COMPACT_TABLE}
						columns={[COPY.name, COPY.where, COPY.left]}
						rows={nearestExpiry(rows, SHOWN).map((row) => ({
							id: row.key,
							cells: [
								<span key="name" dir="ltr" className="font-mono text-sm">
									{row.name}
								</span>,
								<Where key="where" row={row} />,
								<Left key="left" row={row} />,
							],
						}))}
					/>
				);
			}}
		</DataCard>
	);
}
