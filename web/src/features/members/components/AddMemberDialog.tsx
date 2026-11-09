import { zodResolver } from "@hookform/resolvers/zod";
import {
	FormRoot,
	Modal,
	Notice,
	RadioGroupField,
	SubmitButton,
	TextField,
	toast,
} from "@nyxon/nasim";
import { useQueryClient } from "@tanstack/react-query";
import { type Resolver, useForm, useWatch } from "react-hook-form";
import {
	getMembersInvitesQueryKey,
	getMembersListQueryKey,
	useMembersAdd,
	useMembersInvite,
} from "@/api/generated/members/members";
import { errorMessage } from "@/api/transport";
import { t } from "@/strings";
import { type AddValues, addSchema, parseWho, ROLE_OPTIONS, type WhoKind } from "../lib/roles";

const EMPTY: AddValues = { who: "", name: "", role: "admin" };
const KIND_HINT: Record<WhoKind, string> = {
	telegram: t.members.whoKindTelegramId,
	invite: t.members.whoKindInvite,
	account: t.members.whoKindAccount,
};

function KindHint({ form }: { form: ReturnType<typeof useForm<AddValues>> }) {
	const who = parseWho(useWatch({ control: form.control, name: "who" }) ?? "");
	return who ? <p className="text-sm text-muted">{KIND_HINT[who.kind]}</p> : null;
}

// One field, three ways in: a Telegram id or an account username now, a @username as an invite.
export function AddMemberDialog({
	isOpen,
	onOpenChange,
}: {
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const queryClient = useQueryClient();
	const form = useForm<AddValues>({
		resolver: zodResolver(addSchema) as Resolver<AddValues>,
		defaultValues: EMPTY,
	});
	const add = useMembersAdd({
		mutation: {
			onSuccess: (member) => {
				toast.success(
					t.members.added(member.name || String(member.tg_id ?? form.getValues("who"))),
				);
				void queryClient.invalidateQueries({ queryKey: getMembersListQueryKey() });
				change(false);
			},
		},
	});
	const invite = useMembersInvite({
		mutation: {
			onSuccess: (made) => {
				toast.success(t.members.invited(made.tg_username));
				void queryClient.invalidateQueries({ queryKey: getMembersInvitesQueryKey() });
				change(false);
			},
		},
	});
	const error = add.error ?? invite.error;
	function change(open: boolean) {
		onOpenChange(open);
		if (!open) {
			add.reset();
			invite.reset();
			form.reset(EMPTY);
		}
	}
	return (
		<Modal
			isOpen={isOpen}
			onOpenChange={change}
			title={t.members.dialogTitle}
			isBusy={add.isPending || invite.isPending}
		>
			<FormRoot
				form={form}
				className="flex flex-col gap-4"
				onSubmit={(values) => {
					const who = parseWho(values.who);
					if (!who) return;
					const name = values.name.trim() || null;
					if (who.kind === "invite")
						invite.mutate({ data: { tg_username: who.value, name, role: values.role } });
					else add.mutate({ data: { who: who.value, name, role: values.role } });
				}}
			>
				<TextField
					name="who"
					label={t.members.who}
					description={t.members.whoHint}
					isRequired
					autoComplete="off"
					spellCheck={false}
					dir="ltr"
					maxLength={64}
				/>
				<KindHint form={form} />
				<TextField
					name="name"
					label={t.members.name}
					description={t.members.nameHint}
					maxLength={64}
				/>
				<RadioGroupField name="role" label={t.members.role} options={ROLE_OPTIONS} />
				{error ? (
					<Notice tone="danger" role="alert">
						{errorMessage(error)}
					</Notice>
				) : null}
				<SubmitButton>{t.members.submit}</SubmitButton>
			</FormRoot>
		</Modal>
	);
}
