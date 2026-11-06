import {
	EmptyState,
	LinkButton,
	PageHeader,
	SectionCard,
	SkeletonRows,
	StatCard,
} from "@nyxon/nasim";
import { useOverviewGet } from "@/api/generated/overview/overview";
import { IssueList, useIssues } from "@/features/issues";
import { ServerCard, useServers } from "@/features/servers";
import { SslRiskCard } from "@/features/ssl";
import { Loadable } from "@/shared/Loadable";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { formatBytes, formatNumber, t } from "@/strings";

const SHOWN_ISSUES = 5;

function Stats() {
	const overview = useOverviewGet({ query: { refetchInterval: 15_000 } });
	return (
		<Loadable query={overview} skeleton={<SkeletonRows />}>
			{(data) => (
				<section
					aria-label={t.dashboard.statsLabel}
					className="grid grid-cols-2 gap-3 md:grid-cols-4"
				>
					<StatCard label={t.dashboard.online} value={formatNumber(data.online)} />
					<StatCard label={t.dashboard.offline} value={formatNumber(data.offline)} />
					<StatCard label={t.dashboard.pending} value={formatNumber(data.pending)} />
					<StatCard label={t.dashboard.critical} value={formatNumber(data.issues_critical)} />
					<StatCard label={t.dashboard.warning} value={formatNumber(data.issues_warning)} />
					<StatCard label={t.dashboard.download} value={formatBytes(data.rx_bytes_24h)} />
					<StatCard label={t.dashboard.upload} value={formatBytes(data.tx_bytes_24h)} />
				</section>
			)}
		</Loadable>
	);
}

function CurrentIssues() {
	const issues = useIssues();
	return (
		<SectionCard
			title={t.dashboard.issuesTitle}
			actions={
				<LinkButton href="/issues" size="sm" variant="secondary">
					{t.dashboard.issuesAll}
				</LinkButton>
			}
		>
			<Loadable query={issues} skeleton={<SkeletonRows />}>
				{(items) => <IssueList issues={items.slice(0, SHOWN_ISSUES)} />}
			</Loadable>
		</SectionCard>
	);
}

function FleetGrid() {
	const servers = useServers();
	return (
		<SectionCard
			title={t.dashboard.serversTitle}
			actions={
				<LinkButton href="/servers" size="sm" variant="secondary">
					{t.dashboard.serversAll}
				</LinkButton>
			}
		>
			<Loadable query={servers} skeleton={<SkeletonRows />}>
				{(items) =>
					items.length === 0 ? (
						<EmptyState
							title={t.dashboard.noServersTitle}
							description={t.dashboard.noServers}
							action={{ label: t.dashboard.addServer, href: "/servers" }}
						/>
					) : (
						<div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
							{items.map((server) => (
								<ServerCard key={server.id} server={server} />
							))}
						</div>
					)
				}
			</Loadable>
		</SectionCard>
	);
}

export function DashboardPage() {
	useDocumentTitle(t.dashboard.title);
	return (
		<div className="flex flex-col gap-6">
			<PageHeader title={t.dashboard.title} description={t.dashboard.subtitle} />
			<Stats />
			<CurrentIssues />
			<SslRiskCard />
			<FleetGrid />
		</div>
	);
}
