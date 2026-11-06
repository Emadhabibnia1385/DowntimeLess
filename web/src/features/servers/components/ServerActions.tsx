import { Button, ConfirmDialog, Modal, toast } from "@nyxon/nasim";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import type { ServerOut } from "@/api/generated/model";
import { useServersDelete, useServersUpdate } from "@/api/generated/servers/servers";
import { errorMessage } from "@/api/transport";
import { EditIcon, TrashIcon } from "@/shared/icons";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";
import { ServerForm, type ServerFormValues } from "./ServerForm";

const ROLES = ["relay", "exit", "panel", "other"];

// Edit and delete for one server, shown in the page header.
export function ServerActions({ server }: { server: ServerOut }) {
	const refresh = useRefreshAll();
	const navigate = useNavigate();
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
				void refresh();
				void navigate({ to: "/servers", replace: true });
			},
			onError: (error) => {
				setDeleting(false);
				toast.danger(errorMessage(error));
			},
		},
	});
	const defaults: ServerFormValues = {
		name: server.name,
		alias: server.alias,
		role: (ROLES.includes(server.role) ? server.role : "other") as ServerFormValues["role"],
	};
	return (
		<>
			<Button variant="secondary" onPress={() => setEditing(true)}>
				<EditIcon aria-hidden />
				{t.common.edit}
			</Button>
			<Button variant="danger-soft" onPress={() => setDeleting(true)}>
				<TrashIcon aria-hidden />
				{t.common.delete}
			</Button>
			<Modal isOpen={editing} onOpenChange={setEditing} title={t.server.editTitle}>
				<ServerForm
					defaults={defaults}
					submitLabel={t.common.save}
					error={update.error}
					onSubmit={(values) => update.mutate({ serverId: server.id, data: values })}
				/>
			</Modal>
			<ConfirmDialog
				isOpen={deleting}
				onOpenChange={setDeleting}
				tone="danger"
				title={t.server.deleteTitle}
				description={t.server.deleteBody}
				confirmLabel={t.server.danger}
				isPending={remove.isPending}
				onConfirm={() => remove.mutate({ serverId: server.id })}
			/>
		</>
	);
}
