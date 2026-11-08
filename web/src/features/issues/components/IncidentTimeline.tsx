import { StaticTable, StatusChip } from "@nyxon/nasim";
import type { IncidentOut } from "@/api/generated/model";
import { formatDateTime, formatDuration, formatNumber, t } from "@/strings";
import { issueLabel, newestIncidents, severityTone, TIMELINE_LIMIT } from "../lib/history";
import { ServerLabel } from "./ServerLabel";

const SEVERITIES: Record<string, string> = t.severity;
const COLUMNS = t.issueHistory.timelineColumns;

// Each separate occurrence, newest first: start, end (or that it goes on) and duration.
export function IncidentTimeline({
	incidents,
	total,
	flags,
}: {
	incidents: readonly IncidentOut[];
	total: number;
	flags: ReadonlyMap<number, string>;
}) {
	const shown = newestIncidents(incidents);
	const when = (epoch: number) => (
		<span className="whitespace-nowrap text-sm">{formatDateTime(epoch)}</span>
	);
	return (
		<div className="flex flex-col gap-3">
			<StaticTable
				caption={t.issueHistory.timelineLabel}
				className="min-w-[48rem]"
				columns={[
					COLUMNS.start,
					COLUMNS.end,
					COLUMNS.duration,
					COLUMNS.server,
					COLUMNS.issue,
					COLUMNS.severity,
				]}
				rows={shown.map((incident) => ({
					id: String(incident.id),
					cells: [
						when(incident.opened_at),
						incident.closed_at === null ? (
							<StatusChip key="end" tone="warning" label={t.issueHistory.ongoing} size="sm" />
						) : (
							when(incident.closed_at)
						),
						<span key="duration" className="whitespace-nowrap text-sm tabular-nums">
							{formatDuration(incident.duration_s)}
						</span>,
						<ServerLabel
							key="server"
							serverId={incident.server_id}
							name={incident.server_name}
							flag={incident.server_id === null ? "" : (flags.get(incident.server_id) ?? "")}
						/>,
						<span key="issue" className="block max-w-72 whitespace-normal text-sm">
							{issueLabel(incident.code, incident.title)}
						</span>,
						<StatusChip
							key="severity"
							tone={severityTone(incident.severity)}
							label={SEVERITIES[incident.severity] ?? incident.severity}
							size="sm"
						/>,
					],
				}))}
			/>
			{total > TIMELINE_LIMIT ? (
				<p className="text-sm text-muted">
					{t.issueHistory.truncated(formatNumber(shown.length), formatNumber(total))}
				</p>
			) : null}
		</div>
	);
}
