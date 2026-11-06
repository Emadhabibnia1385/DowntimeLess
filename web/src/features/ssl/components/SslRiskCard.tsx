import { LinkButton, SectionCard, SkeletonRows } from "@nyxon/nasim";
import { Loadable } from "@/shared/Loadable";
import { formatNumber, t } from "@/strings";
import { useSsl } from "../api";
import { summarize } from "../lib/status";

// The dashboard's view of the certificates: how many are close to expiry, and a way in.
export function SslRiskCard() {
	const certs = useSsl();
	return (
		<SectionCard
			title={t.dashboard.sslTitle}
			actions={
				<LinkButton href="/ssl" size="sm" variant="secondary">
					{t.dashboard.sslAll}
				</LinkButton>
			}
		>
			<Loadable query={certs} skeleton={<SkeletonRows />}>
				{(rows) => {
					const counts = summarize(rows);
					if (counts.total === 0)
						return <p className="text-sm text-muted">{t.dashboard.sslNone}</p>;
					if (counts.critical + counts.expiring === 0) {
						return <p className="text-sm">{t.dashboard.sslSafe}</p>;
					}
					return (
						<p className="text-sm font-medium">
							{t.dashboard.sslRisk(formatNumber(counts.critical), formatNumber(counts.expiring))}
						</p>
					);
				}}
			</Loadable>
		</SectionCard>
	);
}
