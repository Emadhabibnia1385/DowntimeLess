import { ConfirmDialog, OptionCards, SectionCard, toast } from "@nyxon/nasim";
import { useState } from "react";
import type { ServerOut } from "@/api/generated/model";
import { useServersUpdate } from "@/api/generated/servers/servers";
import { errorMessage } from "@/api/transport";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";

const OPTIONS = [
	{ value: "read", title: t.permissions.read, description: t.permissions.readHint },
	{ value: "safe", title: t.permissions.safe, description: t.permissions.safeHint },
	{ value: "full", title: t.permissions.full, description: t.permissions.fullHint },
];

// The agent's permission level; raising it to safe or full asks for a confirmation first.
export function PermissionSection({
	server,
	canManage,
}: {
	server: ServerOut;
	canManage: boolean;
}) {
	const refresh = useRefreshAll();
	const [wanted, setWanted] = useState<string | null>(null);
	const update = useServersUpdate({
		mutation: {
			onSuccess: () => {
				toast.success(t.common.saved);
				void refresh();
				setWanted(null);
			},
			onError: (error) => toast.danger(errorMessage(error)),
		},
	});
	const apply = (permission: string) =>
		update.mutate({ serverId: server.id, data: { permission } });
	return (
		<SectionCard title={t.server.permissionTitle} description={t.server.permissionHint}>
			<OptionCards
				label={t.server.permission}
				hideLabel
				value={server.permission}
				onChange={(value) => (value === "read" ? apply(value) : setWanted(value))}
				options={canManage ? OPTIONS : OPTIONS.map((option) => ({ ...option, isDisabled: true }))}
			/>
			<ConfirmDialog
				isOpen={wanted !== null}
				onOpenChange={(open) => !open && setWanted(null)}
				title={t.server.permissionConfirmTitle}
				description={t.server.permissionConfirm}
				confirmLabel={t.server.permissionConfirmButton}
				isPending={update.isPending}
				onConfirm={() => {
					if (wanted) apply(wanted);
				}}
			/>
		</SectionCard>
	);
}
