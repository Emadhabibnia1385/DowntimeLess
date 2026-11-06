import { PageHeader, SectionCard } from "@nyxon/nasim";
import { useCanManage } from "@/features/auth";
import { Loadable } from "@/shared/Loadable";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { useServer } from "../api";
import type { Range } from "../lib/chart";
import { displayName, roleLabel } from "../lib/status";
import { InstallCommand } from "./InstallCommand";
import { JobsSection } from "./JobsSection";
import { LiveTiles } from "./LiveTiles";
import { MetricsCharts } from "./MetricsCharts";
import { PermissionSection } from "./PermissionSection";
import { ServerActions } from "./ServerActions";
import { ServerInfo } from "./ServerInfo";
import { ServerStatusChip } from "./ServerStatusChip";

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
						title={displayName(data)}
						description={roleLabel(data.role)}
						backHref="/servers"
						meta={<ServerStatusChip status={data.status} size="md" />}
						actions={canManage ? <ServerActions server={data} /> : undefined}
					/>
					{data.status === "pending" && canManage ? (
						<SectionCard title={t.servers.installTitle}>
							<InstallCommand serverId={data.id} command={null} />
						</SectionCard>
					) : (
						<LiveTiles server={data} />
					)}
					<ServerInfo server={data} />
					<MetricsCharts serverId={data.id} range={range} onRangeChange={onRangeChange} />
					<JobsSection server={data} canManage={canManage} />
					<PermissionSection server={data} canManage={canManage} />
				</div>
			)}
		</Loadable>
	);
}
