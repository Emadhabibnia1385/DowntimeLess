import { ConfirmDialog } from "@nyxon/nasim";
import { t } from "@/strings";
import { useQueueJobs } from "../api";

export type Mutating = "apt_upgrade_safe" | "self_update" | "reboot";

const CONFIRMS: Record<Mutating, { title: string; body: string }> = {
	apt_upgrade_safe: { title: t.server.confirmUpgradeTitle, body: t.server.confirmUpgrade },
	self_update: { title: t.server.confirmSelfUpdateTitle, body: t.server.confirmSelfUpdate },
	reboot: { title: t.server.confirmRebootTitle, body: t.server.confirmReboot },
};

// Every job that changes the server is queued only after this question.
export function JobConfirm({
	serverId,
	kind,
	onClose,
}: {
	serverId: number;
	kind: Mutating | null;
	onClose: () => void;
}) {
	const queue = useQueueJobs(serverId, onClose);
	const confirm = kind ? CONFIRMS[kind] : null;
	return (
		<ConfirmDialog
			isOpen={kind !== null}
			onOpenChange={(open) => !open && onClose()}
			tone={kind === "reboot" ? "danger" : "default"}
			title={confirm?.title ?? ""}
			description={confirm?.body}
			confirmLabel={t.server.confirmRun}
			isPending={queue.isPending}
			onConfirm={() => {
				if (kind) queue.mutate([{ kind, args: {} }]);
			}}
		/>
	);
}
