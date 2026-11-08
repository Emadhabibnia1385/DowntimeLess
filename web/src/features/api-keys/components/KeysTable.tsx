import { Button, ConfirmDialog, type DataColumn, DataTable, StatusChip, toast } from "@nyxon/nasim";
import { useState } from "react";
import type { KeyOut } from "@/api/generated/model";
import { useKeysDelete, useKeysList } from "@/api/generated/keys/keys";
import { errorMessage } from "@/api/transport";
import { TrashIcon } from "@/shared/icons";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { formatDateTime, t } from "@/strings";

// Keys are listed with their prefix only; the full token was shown once at creation.
export function KeysTable() {
	const keys = useKeysList();
	const refresh = useRefreshAll();
	const [removing, setRemoving] = useState<KeyOut | null>(null);
	const remove = useKeysDelete({
		mutation: {
			onSuccess: () => {
				setRemoving(null);
				void refresh();
			},
			onError: (error) => {
				setRemoving(null);
				toast.danger(errorMessage(error));
			},
		},
	});
	const columns: DataColumn<KeyOut>[] = [
		{ id: "name", header: t.apiKeys.name, isRowHeader: true, cell: (key) => key.name },
		{
			id: "prefix",
			header: t.apiKeys.prefix,
			cell: (key) => (
				<span dir="ltr" className="font-mono">
					{key.prefix}
				</span>
			),
		},
		{
			id: "scope",
			header: t.apiKeys.scope,
			cell: (key) => (
				<StatusChip
					tone={key.scope === "full" ? "warning" : "info"}
					label={key.scope === "full" ? t.apiKeys.scopeFull : t.apiKeys.scopeRead}
					size="sm"
				/>
			),
		},
		{ id: "created", header: t.apiKeys.created, cell: (key) => formatDateTime(key.created_at) },
		{
			id: "used",
			header: t.apiKeys.lastUsed,
			cell: (key) => (key.last_used ? formatDateTime(key.last_used) : t.apiKeys.neverUsed),
		},
		{
			id: "actions",
			header: t.common.delete,
			isActions: true,
			cell: (key) => (
				<Button size="sm" variant="danger-soft" onPress={() => setRemoving(key)}>
					<TrashIcon aria-hidden />
					{t.common.delete}
				</Button>
			),
		},
	];
	return (
		<>
			<DataTable
				ariaLabel={t.apiKeys.tableLabel}
				columns={columns}
				rows={keys.data}
				getRowId={(key) => String(key.id)}
				status={keys.isPending ? "loading" : keys.isError ? "error" : "ready"}
				onRetry={() => void keys.refetch()}
				emptyTitle={t.apiKeys.emptyTitle}
				empty={t.apiKeys.empty}
			/>
			<ConfirmDialog
				isOpen={removing !== null}
				onOpenChange={(open) => !open && setRemoving(null)}
				tone="danger"
				title={t.apiKeys.deleteTitle}
				description={t.apiKeys.deleteBody}
				confirmLabel={t.common.delete}
				isPending={remove.isPending}
				onConfirm={() => {
					if (removing) remove.mutate({ keyId: removing.id });
				}}
			/>
		</>
	);
}
