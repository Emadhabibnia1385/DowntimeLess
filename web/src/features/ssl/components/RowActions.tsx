import { Button, ConfirmDialog, Tooltip, toast } from "@nyxon/nasim";
import { useMutation } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import type { SslRow } from "@/api/generated/model";
import { serversCreateJob } from "@/api/generated/servers/servers";
import { useSslCheckDomain, useSslDeleteDomain } from "@/api/generated/ssl/ssl";
import { errorMessage } from "@/api/transport";
import { RefreshIcon, TrashIcon } from "@/shared/icons";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";

function Action({
	label,
	onPress,
	isPending,
	danger,
	children,
}: {
	label: string;
	onPress: () => void;
	isPending?: boolean;
	danger?: boolean;
	children: ReactNode;
}) {
	return (
		<Tooltip>
			<Button
				isIconOnly
				size="sm"
				variant={danger ? "danger-soft" : "secondary"}
				aria-label={label}
				isPending={isPending}
				onPress={onPress}
			>
				{children}
			</Button>
			<Tooltip.Content className="max-w-64 break-normal text-start">{label}</Tooltip.Content>
		</Tooltip>
	);
}

// What one row allows: renew or delete a certbot certificate, or re-check or drop a probed domain.
export function RowActions({ row }: { row: SslRow }) {
	const refresh = useRefreshAll();
	const [asking, setAsking] = useState(false);
	const done = () => {
		setAsking(false);
		void refresh();
	};
	const failed = (error: unknown) => {
		setAsking(false);
		toast.danger(errorMessage(error));
	};
	const job = useMutation({
		mutationFn: (kind: "cert_renew" | "cert_delete") =>
			serversCreateJob(row.server_id as number, { kind, args: { name: row.name } }),
		onSuccess: (_data, kind) => {
			toast.success(kind === "cert_renew" ? t.ssl.renewQueued : t.ssl.deleteCertQueued);
			done();
		},
		onError: failed,
	});
	const check = useSslCheckDomain({
		mutation: {
			onSuccess: () => {
				toast.success(t.ssl.rechecked);
				done();
			},
			onError: failed,
		},
	});
	const remove = useSslDeleteDomain({ mutation: { onSuccess: done, onError: failed } });
	const isFile = row.kind === "file";
	const onServer = isFile && row.server_id !== null;
	const hide = row.kind === "probe" && row.auto;
	return (
		<>
			<div className="flex items-center justify-center gap-1.5">
				{onServer && row.can_renew ? (
					<Action
						label={t.ssl.renewNow}
						isPending={job.isPending}
						onPress={() => job.mutate("cert_renew")}
					>
						<RefreshIcon aria-hidden />
					</Action>
				) : null}
				{row.kind === "probe" && row.id != null ? (
					<Action
						label={t.ssl.recheck}
						isPending={check.isPending}
						onPress={() => check.mutate({ domainId: row.id as number })}
					>
						<RefreshIcon aria-hidden />
					</Action>
				) : null}
				{(onServer && row.can_delete) || (row.kind === "probe" && row.can_delete) ? (
					<Action
						danger
						label={isFile ? t.ssl.deleteCert : hide ? t.ssl.hide : t.common.delete}
						onPress={() => setAsking(true)}
					>
						<TrashIcon aria-hidden />
					</Action>
				) : null}
			</div>
			<ConfirmDialog
				isOpen={asking}
				onOpenChange={setAsking}
				tone="danger"
				title={isFile ? t.ssl.deleteCertTitle : hide ? t.ssl.hideTitle : t.ssl.deleteTitle}
				description={
					isFile
						? t.ssl.deleteCertBody(row.name, row.server_name ?? "")
						: hide
							? t.ssl.hideBody
							: t.ssl.deleteBody
				}
				confirmLabel={isFile ? t.ssl.deleteCert : hide ? t.ssl.hide : t.common.delete}
				isPending={job.isPending || remove.isPending}
				onConfirm={() => {
					if (isFile) job.mutate("cert_delete");
					else if (row.id != null) remove.mutate({ domainId: row.id });
				}}
			/>
		</>
	);
}
