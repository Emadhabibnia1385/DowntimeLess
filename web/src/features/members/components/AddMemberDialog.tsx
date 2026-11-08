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
import { type Resolver, useForm } from "react-hook-form";
import { getMembersListQueryKey, useMembersAdd } from "@/api/generated/members/members";
import { errorMessage } from "@/api/transport";
import { t } from "@/strings";
import { type AddValues, addSchema, ROLE_OPTIONS } from "../lib/roles";

const EMPTY: AddValues = { tgId: "", name: "", role: "admin" };

// A numeric Telegram id, an optional name and a role; the person then signs in with Telegram.
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
				toast.success(t.members.added(member.name || String(member.tg_id)));
				void queryClient.invalidateQueries({ queryKey: getMembersListQueryKey() });
				change(false);
			},
		},
	});
	function change(open: boolean) {
		onOpenChange(open);
		if (!open) {
			add.reset();
			form.reset(EMPTY);
		}
	}
	return (
		<Modal
			isOpen={isOpen}
			onOpenChange={change}
			title={t.members.dialogTitle}
			isBusy={add.isPending}
		>
			<FormRoot
				form={form}
				className="flex flex-col gap-4"
				onSubmit={(values) => {
					const parsed = addSchema.parse(values);
					add.mutate({
						data: { tg_id: Number(parsed.tgId), name: parsed.name || null, role: parsed.role },
					});
				}}
			>
				<TextField
					name="tgId"
					label={t.members.tgId}
					description={t.members.tgIdHint}
					isRequired
					inputMode="numeric"
					autoComplete="off"
					dir="ltr"
					maxLength={20}
				/>
				<TextField
					name="name"
					label={t.members.name}
					description={t.members.nameHint}
					maxLength={64}
				/>
				<RadioGroupField name="role" label={t.members.role} options={ROLE_OPTIONS} />
				{add.error ? (
					<Notice tone="danger" role="alert">
						{errorMessage(add.error)}
					</Notice>
				) : null}
				<SubmitButton>{t.members.submit}</SubmitButton>
			</FormRoot>
		</Modal>
	);
}
