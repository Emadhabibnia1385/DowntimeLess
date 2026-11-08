import {
	Button,
	ConfirmDialog,
	CopyButton,
	type DataColumn,
	DataTable,
	SelectField,
	StatusChip,
	toast,
} from "@nyxon/nasim";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
	getMembersListQueryKey,
	useMembersList,
	useMembersRemove,
	useMembersUpdate,
} from "@/api/generated/members/members";
import type { MemberOut } from "@/api/generated/model";
import { errorMessage } from "@/api/transport";
import { TrashIcon } from "@/shared/icons";
import { formatDateTime, t } from "@/strings";
import { isAssignable, ROLE_OPTIONS } from "../lib/roles";
import { RoleChip } from "./RoleChip";

const nameOf = (member: MemberOut) =>
	member.name || (member.tg_username ? `@${member.tg_username}` : t.members.noName);

/** The owner and I keep our role; everyone else can be changed or removed. */
const editable = (member: MemberOut) => !member.is_me && member.role !== "owner";

function RoleCell({ member }: { member: MemberOut }) {
	const queryClient = useQueryClient();
	const update = useMembersUpdate({
		mutation: {
			onSuccess: () => {
				toast.success(t.members.roleSaved);
				void queryClient.invalidateQueries({ queryKey: getMembersListQueryKey() });
			},
			onError: (error) => toast.danger(errorMessage(error)),
		},
	});
	if (!editable(member) || !isAssignable(member.role)) return <RoleChip role={member.role} />;
	return (
		<SelectField
			label={<span className="sr-only">{t.members.roleOf(nameOf(member))}</span>}
			value={member.role}
			onChange={(role) => {
				if (role && role !== member.role) update.mutate({ userId: member.user_id, data: { role } });
			}}
			options={ROLE_OPTIONS}
			isDisabled={update.isPending}
			className="w-36"
		/>
	);
}

// Everyone who can open this workspace, with their role; the owner changes roles in place.
export function MembersTable() {
	const members = useMembersList();
	const queryClient = useQueryClient();
	const [removing, setRemoving] = useState<MemberOut | null>(null);
	const remove = useMembersRemove({
		mutation: {
			onSuccess: () => {
				setRemoving(null);
				toast.success(t.members.removed);
				void queryClient.invalidateQueries({ queryKey: getMembersListQueryKey() });
			},
			onError: (error) => {
				setRemoving(null);
				toast.danger(errorMessage(error));
			},
		},
	});
	const columns: DataColumn<MemberOut>[] = [
		{
			id: "name",
			header: t.members.colName,
			isRowHeader: true,
			cell: (member) => (
				<span className="flex items-center gap-2">
					<bdi className="font-medium">{nameOf(member)}</bdi>
					{member.is_me ? <StatusChip tone="info" size="sm" label={t.members.you} /> : null}
				</span>
			),
		},
		{
			id: "telegram",
			header: t.members.colTelegram,
			cell: (member) =>
				member.tg_id ? (
					<span dir="ltr" className="inline-flex items-center gap-1">
						<span className="font-mono tabular-nums">{member.tg_id}</span>
						<CopyButton
							value={String(member.tg_id)}
							label={t.members.copyId(nameOf(member))}
							doneLabel=""
							variant="ghost"
							className="size-6 min-h-0 min-w-0 gap-0 p-0 text-[0px] [&_svg]:size-4"
						/>
					</span>
				) : (
					t.common.none
				),
		},
		{ id: "role", header: t.members.colRole, cell: (member) => <RoleCell member={member} /> },
		{
			id: "login",
			header: t.members.colLastLogin,
			cell: (member) =>
				member.last_login ? formatDateTime(member.last_login) : t.members.neverLoggedIn,
		},
		{
			id: "actions",
			header: t.members.colActions,
			isActions: true,
			cell: (member) =>
				editable(member) ? (
					<Button
						size="sm"
						variant="danger-soft"
						aria-label={t.members.removeLabel(nameOf(member))}
						onPress={() => setRemoving(member)}
					>
						<TrashIcon aria-hidden />
						{t.members.remove}
					</Button>
				) : (
					t.common.none
				),
		},
	];
	return (
		<>
			<DataTable
				ariaLabel={t.members.tableLabel}
				columns={columns}
				rows={members.data}
				getRowId={(member) => String(member.user_id)}
				status={members.isPending ? "loading" : members.isError ? "error" : "ready"}
				onRetry={() => void members.refetch()}
			/>
			<ConfirmDialog
				isOpen={removing !== null}
				onOpenChange={(open) => !open && setRemoving(null)}
				tone="danger"
				title={t.members.removeTitle}
				description={removing ? t.members.removeBody(nameOf(removing)) : ""}
				confirmLabel={t.members.remove}
				isPending={remove.isPending}
				onConfirm={() => {
					if (removing) remove.mutate({ userId: removing.user_id });
				}}
			/>
		</>
	);
}
