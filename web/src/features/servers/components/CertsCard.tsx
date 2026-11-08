import { LinkButton, Pager, SectionCard, StatusChip } from "@nyxon/nasim";
import { useState } from "react";
import { certStatus, daysLeftLabel, useSsl } from "@/features/ssl";
import { t } from "@/strings";

// This server's certificates, soonest to expire first, a few per page; hidden when there are none.
const PAGE_SIZE = 5;

export function CertsCard({ serverId }: { serverId: number }) {
	const certs = useSsl();
	const [page, setPage] = useState(1);
	const rows = (certs.data ?? [])
		.filter((row) => row.server_id === serverId)
		.sort(
			(a, b) => (a.days_left ?? Number.MAX_SAFE_INTEGER) - (b.days_left ?? Number.MAX_SAFE_INTEGER),
		);
	if (rows.length === 0) return null;
	const pageCount = Math.ceil(rows.length / PAGE_SIZE);
	const current = Math.min(page, pageCount);
	const shown = rows.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);
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
				{shown.map((row) => {
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
			{pageCount > 1 ? (
				<Pager
					className="mt-3"
					page={current}
					pageCount={pageCount}
					onPrevious={() => setPage(current - 1)}
					onNext={() => setPage(current + 1)}
				/>
			) : null}
		</SectionCard>
	);
}
