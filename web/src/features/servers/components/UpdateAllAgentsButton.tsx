import { Button, ConfirmDialog, toast, Tooltip } from "@nyxon/nasim";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import type { ServerOut } from "@/api/generated/model";
import { serversCreateJob } from "@/api/generated/servers/servers";
import { errorMessage } from "@/api/transport";
import { RefreshIcon } from "@/shared/icons";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { formatNumber, t } from "@/strings";

// Queues an agent update on every online server that runs an older agent.
export function UpdateAllAgentsButton({ servers }: { servers: readonly ServerOut[] }) {
	const refresh = useRefreshAll();
	const [asking, setAsking] = useState(false);
	const targets = servers.filter((server) => server.status === "online" && server.agent_outdated);
	const run = useMutation({
		mutationFn: () =>
			Promise.all(
				targets.map((server) => serversCreateJob(server.id, { kind: "self_update", args: {} })),
			),
		onSuccess: () => {
			toast.success(t.servers.updateAllQueued(formatNumber(targets.length)));
			setAsking(false);
			void refresh();
		},
		onError: (error) => {
			setAsking(false);
			toast.danger(errorMessage(error));
		},
	});
	const press = () => {
		if (targets.length === 0) toast.success(t.servers.updateAllNone);
		else setAsking(true);
	};
	return (
		<>
			<Tooltip>
				<Button isIconOnly variant="secondary" aria-label={t.servers.updateAll} onPress={press}>
					<RefreshIcon aria-hidden />
				</Button>
				<Tooltip.Content className="max-w-64 break-normal text-pretty text-start leading-relaxed">
					{t.servers.updateAllHint}
				</Tooltip.Content>
			</Tooltip>
			<ConfirmDialog
				isOpen={asking}
				onOpenChange={setAsking}
				title={t.servers.updateAllTitle}
				description={t.servers.updateAllBody}
				confirmLabel={t.servers.updateAllConfirm}
				isPending={run.isPending}
				onConfirm={() => run.mutate()}
			/>
		</>
	);
}
