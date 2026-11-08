import { Button, Notice, SectionCard, StaticTable, StatusChip, toast } from "@nyxon/nasim";
import { useChecksDropListener, useChecksHostHealth } from "@/api/generated/checks/checks";
import type { HostHealth, MissingPort } from "@/api/generated/model";
import { errorMessage } from "@/api/transport";
import { IgnoreButton } from "@/features/panel";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { formatNumber, t } from "@/strings";
import { healthRows } from "../lib/hostHealth";

const H = t.server.hostHealth;

function DropPort({ serverId, port }: { serverId: number; port: MissingPort }) {
	const refresh = useRefreshAll();
	const drop = useChecksDropListener();
	const name = `${port.proto}/${port.port}`;
	const press = async () => {
		try {
			await drop.mutateAsync({
				serverId,
				data: { proto: port.proto === "udp" ? "udp" : "tcp", port: port.port },
			});
			void refresh();
		} catch (error) {
			toast.danger(errorMessage(error));
		}
	};
	return (
		<Button
			size="sm"
			variant="secondary"
			aria-label={H.dropLabel(name)}
			isPending={drop.isPending}
			onPress={() => void press()}
		>
			{H.drop}
		</Button>
	);
}

function Body({ data, canManage }: { data: HostHealth; canManage: boolean }) {
	if (!data.has_checks) return <Notice tone="info">{H.noChecks}</Notice>;
	const rows = healthRows(data);
	const missing = data.listeners?.missing ?? [];
	return (
		<div className="flex flex-col gap-4">
			<StaticTable
				caption={H.tableLabel}
				className="min-w-[38rem]"
				columns={[H.columns.part, H.columns.state, H.columns.detail]}
				rows={rows.map((row) => ({
					id: row.key,
					cells: [
						row.label,
						<StatusChip key="state" tone={row.tone} label={row.state} size="sm" />,
						<span key="detail" className="text-sm">
							{row.detail || t.common.none}
						</span>,
					],
				}))}
			/>
			{data.checks_error.length > 0 ? (
				<p className="text-xs text-muted">{H.collectorErrors(data.checks_error.join("، "))}</p>
			) : null}
			{canManage && missing.length > 0 ? (
				<StaticTable
					caption={H.missingLabel}
					columns={[H.columns.port, H.columns.reports, H.columns.action]}
					rows={missing.map((port) => ({
						id: `${port.proto}-${port.port}`,
						cells: [
							<span key="port" dir="ltr" className="font-mono">
								{`${port.proto}/${port.port}${port.proc ? ` ${port.proc}` : ""}`}
							</span>,
							<span key="n" className="tabular-nums">
								{formatNumber(port.missing_reports)}
							</span>,
							<DropPort key="drop" serverId={data.server_id} port={port} />,
						],
					}))}
				/>
			) : null}
			{canManage && (data.containers?.length ?? 0) > 0 ? (
				<StaticTable
					caption={H.containersLabel}
					columns={[H.columns.container, H.columns.state, H.columns.action]}
					rows={(data.containers ?? []).map((box) => ({
						id: box.name,
						cells: [
							<span key="name" dir="ltr" className="font-mono">
								{box.name}
							</span>,
							<span key="state" className="text-sm">
								{[
									box.state,
									box.health,
									box.restarts ? H.restarts(formatNumber(box.restarts)) : null,
								]
									.filter(Boolean)
									.join(" · ")}
							</span>,
							<IgnoreButton
								key="retire"
								serverId={data.server_id}
								kind="container"
								name={box.name}
								ignored={box.retired}
								label={box.retired ? H.unretire : H.retire}
								ariaLabel={(box.retired ? H.unretireLabel : H.retireLabel)(box.name)}
							/>,
						],
					}))}
				/>
			) : null}
		</div>
	);
}

// The agent's read-only host checks: listeners against the baseline, tunnels, containers, kernel.
export function HostHealthCard({ serverId, canManage }: { serverId: number; canManage: boolean }) {
	const health = useChecksHostHealth(serverId, { query: { refetchInterval: 30_000 } });
	if (!health.data) return null;
	return (
		<SectionCard title={H.title} description={H.subtitle}>
			<Body data={health.data} canManage={canManage} />
		</SectionCard>
	);
}
