import { Button, ConfirmDialog, Modal, toast } from "@nyxon/nasim";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import type { ServerOut } from "@/api/generated/model";
import {
	serversCreateJob,
	useServersDelete,
	useServersUpdate,
} from "@/api/generated/servers/servers";
import { errorMessage } from "@/api/transport";
import { EditIcon, RefreshIcon, TrashIcon } from "@/shared/icons";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";
import { categoryValue, toServerPatch } from "../lib/category";
import { AgentVersionMark } from "./AgentVersionMark";
import { ServerForm, type ServerFormValues } from "./ServerForm";

const ROLES = ["exit", "relay", "panel", "panel_only", "other"];

// Edit, update agent and delete for one row of the table; delete is how a pending install goes.
export function ServerRowActions({ server }: { server: ServerOut }) {
	const refresh = useRefreshAll();
	const [editing, setEditing] = useState(false);
	const [deleting, setDeleting] = useState(false);
	const update = useServersUpdate({
		mutation: {
			onSuccess: () => {
				toast.success(t.common.saved);
				void refresh();
				setEditing(false);
			},
		},
	});
	const remove = useServersDelete({
		mutation: {
			onSuccess: () => {
				setDeleting(false);
				void refresh();
			},
			onError: (error) => {
				setDeleting(false);
				toast.danger(errorMessage(error));
			},
		},
	});
	const selfUpdate = useMutation({
		mutationFn: () => serversCreateJob(server.id, { kind: "self_update", args: {} }),
		onSuccess: () => {
			toast.success(t.servers.updateQueued);
			void refresh();
		},
		onError: (error) => toast.danger(errorMessage(error)),
	});
	const defaults: ServerFormValues = {
		name: server.name,
		alias: server.alias,
		category: categoryValue(server.category_id),
		quota_gb: server.quota_gb ?? undefined,
		quota_reset_day: server.quota_reset_day ?? undefined,
		role: (ROLES.includes(server.role) ? server.role : "other") as ServerFormValues["role"],
	};
	const canUpdate = server.status === "online";
	return (
		<div className="flex flex-col items-center gap-1">
			<div className="flex items-center justify-center gap-1">
				{canUpdate ? (
					<Button
						isIconOnly
						size="sm"
						variant={server.agent_outdated ? "primary" : "secondary"}
						isPending={selfUpdate.isPending}
						aria-label={t.servers.updateAgent}
						onPress={() => selfUpdate.mutate()}
					>
						<RefreshIcon aria-hidden />
					</Button>
				) : null}
				<Button
					isIconOnly
					size="sm"
					variant="secondary"
					aria-label={t.common.edit}
					onPress={() => setEditing(true)}
				>
					<EditIcon aria-hidden />
				</Button>
				<Button
					isIconOnly
					size="sm"
					variant="danger-soft"
					aria-label={t.common.delete}
					onPress={() => setDeleting(true)}
				>
					<TrashIcon aria-hidden />
				</Button>
			</div>
			{server.agent_version ? (
				<p className="flex items-center justify-center gap-1 text-xs text-muted">
					<RefreshIcon aria-hidden className="size-3.5" />
					<span>{t.servers.version}</span>
					<span dir="ltr" className="font-mono">
						{server.agent_version}
					</span>
					<AgentVersionMark outdated={Boolean(server.agent_outdated)} />
				</p>
			) : null}
			<Modal isOpen={editing} onOpenChange={setEditing} title={t.servers.editRowTitle}>
				<ServerForm
					defaults={defaults}
					submitLabel={t.common.save}
					withQuota
					error={update.error}
					onSubmit={(values) => update.mutate({ serverId: server.id, data: toServerPatch(values) })}
				/>
			</Modal>
			<ConfirmDialog
				isOpen={deleting}
				onOpenChange={setDeleting}
				tone="danger"
				title={t.servers.deleteRowTitle}
				description={t.servers.deleteRowBody}
				confirmLabel={t.common.delete}
				isPending={remove.isPending}
				onConfirm={() => remove.mutate({ serverId: server.id })}
			/>
		</div>
	);
}
