import { EmptyState, SectionCard, StaticTable } from "@nyxon/nasim";
import type { LinkRow } from "@/api/generated/model";
import { useLinksTraffic } from "@/api/generated/links/links";
import { useServers, whereOf } from "@/features/servers";
import { Loadable } from "@/shared/Loadable";
import { formatBytes, t } from "@/strings";
import type { Window } from "../lib/period";
import { ShareBar } from "./ShareBar";

const REFRESH_MS = 60_000;
const MAX_ROWS = 30;

// Bytes between each server and each peer server in the window, measured on the server side.
export function LinksCard({ window }: { window: Window }) {
	const links = useLinksTraffic(
		{ since: window.since, until: window.until },
		{ query: { refetchInterval: REFRESH_MS } },
	);
	const servers = useServers();
	const countryOf = new Map((servers.data ?? []).map((server) => [server.id, server.country]));
	const flag = (id: number | null, role: string | null) =>
		id === null ? "" : whereOf({ role: role ?? "other", country: countryOf.get(id) }).flag;
	return (
		<SectionCard title={t.traffic.links.title} description={t.traffic.links.description}>
			<Loadable query={links}>
				{(data) => {
					if (data.links.length === 0) {
						return (
							<EmptyState title={t.traffic.links.emptyTitle} description={t.traffic.links.empty} />
						);
					}
					const total = data.links.reduce((sum, row) => sum + row.in_bytes + row.out_bytes, 0);
					const rows: readonly LinkRow[] = data.links.slice(0, MAX_ROWS);
					return (
						<div className="flex flex-col gap-2">
							<StaticTable
								className="min-w-[40rem] [&_td]:whitespace-nowrap [&_th]:whitespace-nowrap"
								caption={t.traffic.links.tableLabel}
								columns={[
									t.traffic.links.server,
									t.traffic.links.peer,
									t.traffic.links.in,
									t.traffic.links.out,
									t.traffic.total,
									t.traffic.links.share,
								]}
								rows={rows.map((row) => ({
									id: `${row.server_id}:${row.peer_ip}`,
									cells: [
										<span key="s">
											<span aria-hidden>{flag(row.server_id, row.server_role)}</span>{" "}
											{row.server_name}
										</span>,
										<span key="p" className="inline-flex flex-col">
											<span>
												<span aria-hidden>{flag(row.peer_id, row.peer_role)}</span>{" "}
												{row.peer_name ?? t.traffic.links.unknownPeer}
											</span>
											<span dir="ltr" className="text-start font-mono text-xs text-muted">
												{row.peer_ip}
											</span>
										</span>,
										formatBytes(row.in_bytes),
										formatBytes(row.out_bytes),
										<strong key="t">{formatBytes(row.in_bytes + row.out_bytes)}</strong>,
										<ShareBar
											key="share"
											percent={total > 0 ? ((row.in_bytes + row.out_bytes) * 100) / total : 0}
										/>,
									],
								}))}
							/>
							{data.links.length > MAX_ROWS ? (
								<p className="text-xs text-muted">{t.traffic.links.truncated(MAX_ROWS)}</p>
							) : null}
						</div>
					);
				}}
			</Loadable>
		</SectionCard>
	);
}
