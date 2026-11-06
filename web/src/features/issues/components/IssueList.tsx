import { EmptyState, KeyValueList, LinkButton, StatusChip } from "@nyxon/nasim";
import type { Issue } from "@/api/generated/model";
import { ForwardIcon } from "@/shared/icons";
import { t } from "@/strings";
import { evidenceRows } from "../lib/evidence";

const TONES = { critical: "danger", warning: "warning", info: "info" } as const;
const LABELS: Record<string, string> = t.severity;

function IssueItem({ issue }: { issue: Issue }) {
	const tone = TONES[issue.severity as keyof typeof TONES] ?? "neutral";
	return (
		<li className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
			<div className="flex flex-wrap items-center gap-2">
				<StatusChip tone={tone} label={LABELS[issue.severity] ?? issue.severity} size="sm" />
				<span className="text-sm text-muted">{issue.server_name}</span>
			</div>
			<h3 className="font-semibold">{issue.title}</h3>
			<KeyValueList
				layout="split"
				items={evidenceRows(issue.evidence).map((row) => ({
					label: row.label,
					value: row.value,
					ltr: row.ltr,
				}))}
			/>
			<p className="text-sm">
				<span className="font-medium">{t.issues.suggestion}: </span>
				{issue.suggestion}
			</p>
			<div>
				<LinkButton href={`/servers/${issue.server_id}`} size="sm" variant="secondary">
					{t.issues.openServer}
					<ForwardIcon aria-hidden className="rtl:rotate-180" />
				</LinkButton>
			</div>
		</li>
	);
}

// Problems with their evidence and a suggested next step, worst first (the master sorts them).
export function IssueList({ issues }: { issues: Issue[] }) {
	if (issues.length === 0) {
		return <EmptyState title={t.issues.emptyTitle} description={t.issues.empty} />;
	}
	return (
		<ul aria-label={t.issues.listLabel} className="grid gap-3 lg:grid-cols-2">
			{issues.map((issue) => (
				<IssueItem key={issue.id} issue={issue} />
			))}
		</ul>
	);
}
