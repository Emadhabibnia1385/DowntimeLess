import { Button, SectionCard, StaticTable, toast } from "@nyxon/nasim";
import { useQueryClient } from "@tanstack/react-query";
import {
	getMembersInvitesQueryKey,
	getMembersListQueryKey,
	useMembersApproveInvite,
	useMembersCancelInvite,
	useMembersInvites,
	useMembersRejectInvite,
} from "@/api/generated/members/members";
import type { InviteOut } from "@/api/generated/model";
import { errorMessage } from "@/api/transport";
import { formatDateTime, formatNumber, t } from "@/strings";
import { RoleChip } from "./RoleChip";

function Cancel({ invite }: { invite: InviteOut }) {
	const queryClient = useQueryClient();
	const cancel = useMembersCancelInvite({
		mutation: {
			onSuccess: () => {
				toast.success(t.members.inviteCancelled);
				void queryClient.invalidateQueries({ queryKey: getMembersInvitesQueryKey() });
			},
			onError: (error) => toast.danger(errorMessage(error)),
		},
	});
	return (
		<Button
			size="sm"
			variant="secondary"
			isPending={cancel.isPending}
			aria-label={t.members.cancelInviteLabel(invite.tg_username)}
			onPress={() => cancel.mutate({ inviteId: invite.id })}
		>
			{t.members.cancelInvite}
		</Button>
	);
}

function Decide({ invite }: { invite: InviteOut }) {
	const queryClient = useQueryClient();
	const done = (message: string) => () => {
		toast.success(message);
		void queryClient.invalidateQueries({ queryKey: getMembersInvitesQueryKey() });
		void queryClient.invalidateQueries({ queryKey: getMembersListQueryKey() });
	};
	const onError = (error: unknown) => toast.danger(errorMessage(error));
	const approve = useMembersApproveInvite({
		mutation: { onSuccess: done(t.members.inviteApproved), onError },
	});
	const reject = useMembersRejectInvite({
		mutation: { onSuccess: done(t.members.inviteRejected), onError },
	});
	return (
		<span className="flex flex-wrap gap-2">
			<Button
				size="sm"
				isPending={approve.isPending}
				aria-label={t.members.approveLabel(invite.tg_username)}
				onPress={() => approve.mutate({ inviteId: invite.id })}
			>
				{t.members.approve}
			</Button>
			<Button
				size="sm"
				variant="secondary"
				isPending={reject.isPending}
				aria-label={t.members.rejectLabel(invite.tg_username)}
				onPress={() => reject.mutate({ inviteId: invite.id })}
			>
				{t.members.reject}
			</Button>
		</span>
	);
}

// Invites by Telegram username that nobody has claimed yet; hidden while there are none.
export function InvitesCard() {
	const invites = useMembersInvites();
	const rows = invites.data ?? [];
	if (rows.length === 0) return null;
	return (
		<SectionCard title={t.members.invitesTitle} description={t.members.invitesHint}>
			<StaticTable
				caption={t.members.invitesLabel}
				className="min-w-[36rem]"
				columns={[
					t.members.colInvitee,
					t.members.colRole,
					t.members.colRequest,
					t.members.colExpires,
					t.members.colActions,
				]}
				rows={rows.map((invite) => ({
					id: String(invite.id),
					cells: [
						<span key="who" dir="ltr" className="font-mono text-sm">
							@{invite.tg_username}
							{invite.name ? <span className="font-sans text-muted"> · {invite.name}</span> : null}
						</span>,
						<RoleChip key="role" role={invite.role} />,
						<span key="req" dir="auto" className="text-sm">
							{invite.pending_tg_id
								? t.members.requestWho(
										formatNumber(invite.pending_tg_id),
										invite.pending_name ?? "",
									)
								: t.members.noRequest}
						</span>,
						<span key="exp" className="tabular-nums">
							{formatDateTime(invite.expires_at)}
						</span>,
						<span key="act" className="flex flex-wrap gap-2">
							{invite.pending_tg_id ? <Decide invite={invite} /> : null}
							<Cancel invite={invite} />
						</span>,
					],
				}))}
			/>
		</SectionCard>
	);
}
