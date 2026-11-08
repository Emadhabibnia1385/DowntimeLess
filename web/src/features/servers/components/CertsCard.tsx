import { LinkButton, SectionCard, StatusChip } from "@nyxon/nasim";
import { certStatus, daysLeftLabel, useSsl } from "@/features/ssl";
import { t } from "@/strings";

// The certificates found on this server, soonest to expire first; hidden when there are none.
export function CertsCard({ serverId }: { serverId: number }) {
	const certs = useSsl();
	const rows = (certs.data ?? [])
		.filter((row) => row.server_id === serverId)
		.sort(
			(a, b) => (a.days_left ?? Number.MAX_SAFE_INTEGER) - (b.days_left ?? Number.MAX_SAFE_INTEGER),
		);
	if (rows.length === 0) return null;
	return (
		<SectionCard
			title={t.server.certsTitle}
			actions={
				<LinkButton href="/ssl" size="sm" variant="secondary">
					{t.server.certsAll}
				</LinkButton>
			}
		>
			<ul className="flex flex-col divide-y divide-separator">
				{rows.map((row) => {
					const status = certStatus(row);
					const label = row.days_left == null ? status.label : daysLeftLabel(row.days_left);
					return (
						<li key={row.key} className="flex items-center justify-between gap-3 py-2">
							<span dir="ltr" className="min-w-0 truncate font-mono text-sm">
								{row.name}
							</span>
							<StatusChip tone={status.tone} label={label} size="sm" />
						</li>
					);
				})}
			</ul>
		</SectionCard>
	);
}
