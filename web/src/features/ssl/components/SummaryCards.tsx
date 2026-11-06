import { SkeletonRows, StatCard } from "@nyxon/nasim";
import { Loadable } from "@/shared/Loadable";
import { formatNumber, t } from "@/strings";
import { useSsl } from "../api";
import { summarize } from "../lib/status";

export function SummaryCards() {
	const certs = useSsl();
	return (
		<Loadable query={certs} skeleton={<SkeletonRows />}>
			{(rows) => {
				const counts = summarize(rows);
				return (
					<section aria-label={t.ssl.statsLabel} className="grid grid-cols-2 gap-3 md:grid-cols-4">
						<StatCard label={t.ssl.total} value={formatNumber(counts.total)} />
						<StatCard label={t.ssl.expiring} value={formatNumber(counts.expiring)} />
						<StatCard label={t.ssl.critical} value={formatNumber(counts.critical)} />
						<StatCard label={t.ssl.autoRenewOff} value={formatNumber(counts.autoRenewOff)} />
					</section>
				);
			}}
		</Loadable>
	);
}
