import { Button, SectionCard, StaticTable, toast } from "@nyxon/nasim";
import { useQueryClient } from "@tanstack/react-query";
import {
	getMembersInvitesQueryKey,
	useMembersCancelInvite,
	useMembersInvites,
} from "@/api/generated/members/members";
import type { InviteOut } from "@/api/generated/model";
import { errorMessage } from "@/api/transport";
import { formatDateTime, t } from "@/strings";
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

// Invites by Telegram username that nobody has claimed yet; hidden while there are none.
export function InvitesCard() {
	const invites = useMembersInvites();
	const rows = invites.data ?? [];
	if (rows.length === 0) return null;
	return (
		<SectionCard title={t.members.invitesTitle} description={t.members.invitesHint}>
			<StaticTable
				caption={t.members.invitesLabel}
				className="min-w-[28rem]"
				columns={[
					t.members.colInvitee,
					t.members.colRole,
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
						<span key="exp" className="tabular-nums">
							{formatDateTime(invite.expires_at)}
						</span>,
						<Cancel key="cancel" invite={invite} />,
					],
				}))}
			/>
		</SectionCard>
	);
}
