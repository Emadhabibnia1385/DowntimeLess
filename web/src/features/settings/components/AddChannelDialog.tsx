import { zodResolver } from "@hookform/resolvers/zod";
import { FormRoot, Modal, Notice, SubmitButton, TextField, toast } from "@nyxon/nasim";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useTelegramCreateChannel } from "@/api/generated/telegram/telegram";
import { errorMessage } from "@/api/transport";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";

// A numeric chat id (-100…) or a public @username; a t.me link is accepted too.
const CHAT_ID =
	/^(-?\d{5,16}|@[A-Za-z][A-Za-z0-9_]{4,31}|(https?:\/\/)?t\.me\/[A-Za-z][A-Za-z0-9_]{4,31}\/?)$/;

const schema = z.object({
	name: z.string().trim().min(1, { error: t.channels.nameRequired }).max(64),
	chat_id: z.string().trim().regex(CHAT_ID, { error: t.channels.chatIdInvalid }),
});
type Values = z.input<typeof schema>;

const EMPTY: Values = { name: "", chat_id: "" };

// The master checks the id again; the bot token never reaches the browser.
export function AddChannelDialog({
	isOpen,
	onOpenChange,
}: {
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const refresh = useRefreshAll();
	const form = useForm<Values, unknown, z.output<typeof schema>>({
		resolver: zodResolver(schema),
		defaultValues: EMPTY,
	});
	const add = useTelegramCreateChannel({
		mutation: {
			onSuccess: () => {
				toast.success(t.channels.added);
				void refresh();
				change(false);
			},
		},
	});
	const change = (open: boolean) => {
		onOpenChange(open);
		if (!open) {
			add.reset();
			form.reset(EMPTY);
		}
	};
	return (
		<Modal isOpen={isOpen} onOpenChange={change} title={t.channels.addTitle}>
			<FormRoot
				form={form}
				className="flex flex-col gap-4"
				onSubmit={(values) => add.mutate({ data: values })}
			>
				<p className="text-sm text-muted">{t.channels.hint}</p>
				<TextField
					name="name"
					label={t.channels.name}
					description={t.channels.nameHint}
					isRequired
					maxLength={64}
				/>
				<TextField
					name="chat_id"
					label={t.channels.chatId}
					description={t.channels.chatIdHint}
					dir="ltr"
					isRequired
					autoComplete="off"
					spellCheck={false}
				/>
				{add.error ? (
					<Notice tone="danger" role="alert">
						{errorMessage(add.error)}
					</Notice>
				) : null}
				<SubmitButton>{t.channels.submit}</SubmitButton>
			</FormRoot>
		</Modal>
	);
}
