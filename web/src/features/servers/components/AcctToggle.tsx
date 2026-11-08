import { SwitchField, toast } from "@nyxon/nasim";
import type { ServerOut } from "@/api/generated/model";
import { useServersUpdate } from "@/api/generated/servers/servers";
import { errorMessage } from "@/api/transport";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";

// Switches the counter-only nftables table on or off; the agent applies it at its next report.
export function AcctToggle({ server }: { server: ServerOut }) {
	const refresh = useRefreshAll();
	const update = useServersUpdate({
		mutation: {
			onSuccess: () => {
				toast.success(t.common.saved);
				void refresh();
			},
			onError: (error) => toast.danger(errorMessage(error)),
		},
	});
	return (
		<div className="flex flex-col gap-1 rounded-xl border border-border px-3 py-2.5">
			<SwitchField
				label={t.server.acctTitle}
				description={t.server.acctHint}
				value={server.acct_on ?? false}
				onChange={(on) => update.mutate({ serverId: server.id, data: { acct_on: on } })}
				isDisabled={update.isPending}
			/>
		</div>
	);
}
