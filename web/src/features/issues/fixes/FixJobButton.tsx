import { Button, ConfirmDialog } from "@nyxon/nasim";
import { useState } from "react";
import { useCanManage } from "@/features/auth/session";
import { useQueueJobs } from "@/features/servers/api";
import { t } from "@/strings";
import { type Fix, fixCommand } from "./lib";

const F = t.fixJobs;

// Admins only (the master refuses API keys); the exact commands show before anything is queued.
export function FixJobButton({
	serverId,
	server,
	title,
	fix,
}: {
	serverId: number;
	server: string;
	title: string;
	fix: Fix;
}) {
	const allowed = useCanManage();
	const [open, setOpen] = useState(false);
	const queue = useQueueJobs(serverId, () => setOpen(false));
	if (!allowed) return null;
	return (
		<>
			<Button
				size="sm"
				variant="secondary"
				aria-label={F.actionFor(title, server)}
				onPress={() => setOpen(true)}
			>
				{F.action}
			</Button>
			<ConfirmDialog
				isOpen={open}
				onOpenChange={setOpen}
				tone="danger"
				title={F.titles[fix.kind]}
				description={F.bodies[fix.kind]}
				confirmLabel={F.confirm}
				isPending={queue.isPending}
				onConfirm={() => queue.mutate([{ kind: fix.kind, args: fix.args }])}
			>
				<div className="flex flex-col gap-2">
					<span className="text-sm">{F.commandLabel}</span>
					<pre
						dir="ltr"
						className="whitespace-pre-wrap rounded-xl border border-border bg-surface-secondary p-3 text-start font-mono text-xs leading-5 [overflow-wrap:anywhere]"
					>
						{fixCommand(fix)}
					</pre>
				</div>
			</ConfirmDialog>
		</>
	);
}
