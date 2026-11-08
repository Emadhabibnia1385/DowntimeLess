import { EmptyState, Notice, PageHeader, SectionCard, StaticTable, StatusChip } from "@nyxon/nasim";
import type { PanelHost } from "@/api/generated/model";
import { useCanManage } from "@/features/auth";
import { Loadable } from "@/shared/Loadable";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { formatDateTime, formatNumber, formatRelativeTime, t } from "@/strings";
import { usePanel } from "../api";
import { USER_STATUSES } from "../lib/view";
import { IgnoreButton } from "./IgnoreButton";
import { NodesTable } from "./NodesTable";
import { ResellersTable } from "./ResellersTable";

const P = t.panel;
const USER_LABELS: Record<string, string> = P.users.status;

function UsersTable({ counts }: { counts: Record<string, number> }) {
	const keys = [
		...USER_STATUSES.filter((key) => key in counts),
		...Object.keys(counts).filter((k) => !USER_STATUSES.includes(k as never)),
	];
	const total = keys.reduce((sum, key) => sum + (counts[key] ?? 0), 0);
	return (
		<StaticTable
			caption={P.users.tableLabel}
			columns={[P.users.columns.status, P.users.columns.count]}
			rows={[
				...keys.map((key) => ({
					id: key,
					cells: [
						USER_LABELS[key] ?? key,
						<span key="n" className="tabular-nums">
							{formatNumber(counts[key] ?? 0)}
						</span>,
					],
				})),
				{
					id: "total",
					cells: [
						P.users.total,
						<span key="n" className="font-semibold tabular-nums">
							{formatNumber(total)}
						</span>,
					],
				},
			]}
		/>
	);
}

function InboundsTable({ host, canManage }: { host: PanelHost; canManage: boolean }) {
	const I = P.inbounds;
	if (host.inbounds_without_group.length === 0)
		return <p className="text-sm text-muted">{I.empty}</p>;
	return (
		<StaticTable
			caption={I.tableLabel}
			columns={
				canManage
					? [I.columns.tag, I.columns.state, I.columns.actions]
					: [I.columns.tag, I.columns.state]
			}
			rows={host.inbounds_without_group.map((item) => ({
				id: item.tag,
				cells: [
					<span key="tag" dir="ltr" className="font-mono">
						{item.tag}
					</span>,
					<StatusChip
						key="state"
						tone={item.ignored ? "neutral" : "warning"}
						label={item.ignored ? I.acked : I.watching}
						size="sm"
					/>,
					...(canManage
						? [
								<IgnoreButton
									key="action"
									serverId={host.server_id}
									kind="inbound"
									name={item.tag}
									ignored={item.ignored}
									label={item.ignored ? I.unack : I.ack}
									ariaLabel={(item.ignored ? I.unackLabel : I.ackLabel)(item.tag)}
								/>,
							]
						: []),
				],
			}))}
		/>
	);
}

function HostSection({
	host,
	dropAt,
	canManage,
}: {
	host: PanelHost;
	dropAt: number;
	canManage: boolean;
}) {
	const live = host.nodes.filter((node) => node.enabled && !node.ignored);
	const connected = live.filter((node) => node.status === "connected").length;
	const meta = [
		host.version ? P.version(host.version) : null,
		host.reported_at ? P.reported(formatRelativeTime(host.reported_at)) : null,
		host.hour_start ? P.hourOf(formatDateTime(host.hour_start)) : null,
	].filter(Boolean);
	return (
		<section className="flex flex-col gap-4" aria-label={P.hostTitle(host.server_name)}>
			<div className="flex flex-col gap-1">
				<h2 className="text-lg font-semibold">{P.hostTitle(host.server_name)}</h2>
				<p className="text-sm text-muted">{meta.join(" · ")}</p>
			</div>
			{host.panel_error ? (
				<Notice tone="danger" role="alert">
					{P.readError(host.panel_error)}
				</Notice>
			) : null}
			{host.errors.length > 0 ? (
				<Notice tone="warning">{P.partErrors(host.errors.join("، "))}</Notice>
			) : null}
			{host.available ? (
				<>
					<SectionCard
						title={P.nodes.title}
						description={P.nodes.summary(
							formatNumber(connected),
							formatNumber(live.length),
							formatNumber(host.nodes.length),
						)}
					>
						<NodesTable
							serverId={host.server_id}
							nodes={host.nodes}
							dropAt={dropAt}
							canManage={canManage}
						/>
					</SectionCard>
					<SectionCard
						title={P.resellers.title}
						description={P.resellers.summary(
							formatNumber(host.resellers.filter((row) => row.level !== "ok").length),
							formatNumber(host.resellers.length),
						)}
					>
						<ResellersTable rows={host.resellers} />
					</SectionCard>
					<div className="grid items-start gap-6 lg:grid-cols-2">
						<SectionCard title={P.users.title}>
							{host.user_status ? (
								<UsersTable counts={host.user_status} />
							) : (
								<p className="text-sm text-muted">{P.users.empty}</p>
							)}
						</SectionCard>
						<SectionCard title={P.inbounds.title} description={P.inbounds.hint}>
							<InboundsTable host={host} canManage={canManage} />
						</SectionCard>
					</div>
				</>
			) : null}
		</section>
	);
}

// The read-only PasarGuard view: what the panel host's agent read from the panel's own database.
export function PanelPage() {
	useDocumentTitle(P.title);
	const canManage = useCanManage();
	const panel = usePanel();
	return (
		<div className="flex flex-col gap-6">
			<PageHeader title={P.title} description={P.subtitle} />
			<Loadable query={panel}>
				{(data) =>
					data.panels.length === 0 ? (
						<EmptyState title={P.emptyTitle} description={P.empty} />
					) : (
						<div className="flex flex-col gap-10">
							{data.panels.map((host) => (
								<HostSection
									key={host.server_id}
									host={host}
									dropAt={data.node_drop_pct}
									canManage={canManage}
								/>
							))}
						</div>
					)
				}
			</Loadable>
		</div>
	);
}
