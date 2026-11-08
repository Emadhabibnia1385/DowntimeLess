import { PageHeader, SectionCard } from "@nyxon/nasim";
import { useCanManage } from "@/features/auth";
import { Loadable } from "@/shared/Loadable";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { useServer } from "../api";
import type { Range } from "../lib/chart";
import { displayName } from "../lib/status";
import { whereOf } from "../lib/where";
import { CertsCard } from "./CertsCard";
import { HistoryCard } from "./HistoryCard";
import { InstallCommand } from "./InstallCommand";
import { LiveTiles } from "./LiveTiles";
import { OperationsCard } from "./OperationsCard";
import { RecentJobs } from "./RecentJobs";
import { RelayPingCard } from "./RelayPingCard";
import { ServerActions } from "./ServerActions";
import { ServerBadges } from "./ServerBadges";
import { ServerInfo } from "./ServerInfo";
import { ServerTrafficCard } from "./ServerTrafficCard";

export function ServerDetailPage({
	serverId,
	range,
	onRangeChange,
}: {
	serverId: number;
	range: Range;
	onRangeChange: (range: Range) => void;
}) {
	const server = useServer(serverId);
	const canManage = useCanManage();
	useDocumentTitle(server.data ? displayName(server.data) : t.servers.title);
	return (
		<Loadable query={server}>
			{(data) => (
				<div className="flex flex-col gap-6">
					<PageHeader
						title={`${whereOf({ ...data, org: null }).flag} ${displayName(data)}`.trim()}
						backHref="/servers"
						meta={<ServerBadges server={data} />}
						actions={canManage ? <ServerActions server={data} /> : undefined}
					/>
					{data.status === "pending" && canManage ? (
						<SectionCard title={t.servers.installTitle}>
							<InstallCommand serverId={data.id} command={null} />
						</SectionCard>
					) : (
						<LiveTiles server={data} />
					)}
					<div className="grid items-start gap-6 lg:grid-cols-2">
						<div className="flex min-w-0 flex-col gap-6 lg:order-2">
							<ServerInfo server={data} />
							<CertsCard serverId={data.id} />
						</div>
						<div className="min-w-0 lg:order-1">
							<OperationsCard server={data} canManage={canManage} />
						</div>
					</div>
					<SectionCard title={t.server.recentJobs}>
						<RecentJobs serverId={data.id} />
					</SectionCard>
					<div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_17rem]">
						<div className="min-w-0">
							<HistoryCard
								serverId={data.id}
								range={range}
								onRangeChange={onRangeChange}
								cores={data.system?.cpu_cores ?? data.latest.cpu_cores}
							/>
						</div>
						<div className="order-first min-w-0 xl:order-none">
							<ServerTrafficCard serverId={data.id} />
						</div>
					</div>
					{data.role === "relay" ? <RelayPingCard serverId={data.id} /> : null}
				</div>
			)}
		</Loadable>
	);
}
