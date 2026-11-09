import { Button, Collapsible, StaticTable, StatusChip, toast } from "@nyxon/nasim";
import type { Issue } from "@/api/generated/model";
import { useIssuesUnack } from "@/api/generated/issues/issues";
import { errorMessage } from "@/api/transport";
import { useCanCheck } from "@/features/auth/session";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { formatNumber, t } from "@/strings";
import { severityTone } from "../lib/history";
import { ServerLabel } from "../components/ServerLabel";
import { GuideButton } from "../guides";
import { familyOf } from "../lib/group";
import { untilText } from "./lib";

const C = t.issueAcks;
const SEVERITIES: Record<string, string> = t.severity;

function Undo({ issue }: { issue: Issue }) {
	const refresh = useRefreshAll();
	const unack = useIssuesUnack({
		mutation: {
			onSuccess: () => {
				toast.success(C.undone);
				void refresh();
			},
			onError: (error) => toast.danger(errorMessage(error)),
		},
	});
	return (
		<Button
			size="sm"
			variant="secondary"
			isPending={unack.isPending}
			onPress={() => unack.mutate({ params: { key: issue.id } })}
		>
			{C.undo}
		</Button>
	);
}

// Acknowledged issues sit apart and closed by default: they are known, so they stay out of the way.
export function AckedSection({ issues }: { issues: readonly Issue[] }) {
	const canUndo = useCanCheck();
	if (issues.length === 0) return null;
	const columns = [
		C.columns.server,
		C.columns.issue,
		C.columns.by,
		C.columns.until,
		C.columns.note,
	];
	return (
		<Collapsible title={C.groupTitle(formatNumber(issues.length))} description={C.groupHint}>
			<StaticTable
				caption={C.tableLabel}
				className="min-w-[40rem]"
				columns={canUndo ? [...columns, C.columns.undo] : columns}
				rows={issues.map((issue) => ({
					id: issue.id,
					cells: [
						<ServerLabel
							key="server"
							serverId={issue.server_id}
							name={issue.server_name}
							flag=""
						/>,
						<span key="issue" className="flex flex-col items-start gap-1">
							<StatusChip
								tone={severityTone(issue.severity)}
								label={SEVERITIES[issue.severity] ?? issue.severity}
								size="sm"
							/>
							<span className="whitespace-normal text-sm">{issue.title}</span>
							<GuideButton target={{ code: familyOf(issue.code), title: issue.title }} />
						</span>,
						issue.acked_by || t.common.none,
						<span key="until" className="whitespace-nowrap tabular-nums">
							{untilText(issue)}
						</span>,
						<span key="note" className="block max-w-64 whitespace-normal text-sm text-muted">
							{issue.ack_note || t.common.none}
						</span>,
						...(canUndo ? [<Undo key="undo" issue={issue} />] : []),
					],
				}))}
			/>
		</Collapsible>
	);
}
