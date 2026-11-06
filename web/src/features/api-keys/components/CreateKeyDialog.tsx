import { zodResolver } from "@hookform/resolvers/zod";
import {
	Button,
	CopyField,
	FormRoot,
	Modal,
	Notice,
	RadioGroupField,
	SubmitButton,
	TextField,
} from "@nyxon/nasim";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { KeyCreated } from "@/api/generated/model";
import { useKeysCreate } from "@/api/generated/keys/keys";
import { errorMessage } from "@/api/transport";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";

const schema = z.object({
	name: z.string().trim().min(1, { error: t.apiKeys.nameRequired }).max(64),
	scope: z.enum(["read", "operate"]),
});
type Values = z.input<typeof schema>;

const scopes = [
	{ value: "read", label: t.apiKeys.scopeRead, description: t.apiKeys.scopeReadHint },
	{ value: "operate", label: t.apiKeys.scopeOperate, description: t.apiKeys.scopeOperateHint },
];

// Two steps in one dialog: name the key, then show its token once.
export function CreateKeyDialog({
	isOpen,
	onOpenChange,
}: {
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const [created, setCreated] = useState<KeyCreated | null>(null);
	const refresh = useRefreshAll();
	const create = useKeysCreate({
		mutation: {
			onSuccess: (key) => {
				setCreated(key);
				void refresh();
			},
		},
	});
	const form = useForm<Values>({
		resolver: zodResolver(schema),
		defaultValues: { name: "", scope: "read" },
	});
	const change = (open: boolean) => {
		onOpenChange(open);
		if (!open) {
			setCreated(null);
			create.reset();
			form.reset();
		}
	};
	return (
		<Modal
			isOpen={isOpen}
			onOpenChange={change}
			title={created ? t.apiKeys.createdTitle : t.apiKeys.createTitle}
			isDismissable={created === null}
			footer={created ? <Button onPress={() => change(false)}>{t.common.done}</Button> : undefined}
		>
			{created ? (
				<div className="flex flex-col gap-4">
					<Notice tone="warning">{t.apiKeys.createdBody}</Notice>
					<CopyField label={t.apiKeys.token} value={created.token} />
				</div>
			) : (
				<FormRoot
					form={form}
					className="flex flex-col gap-4"
					onSubmit={(values) =>
						create.mutate({ data: { name: values.name.trim(), scope: values.scope } })
					}
				>
					<TextField name="name" label={t.apiKeys.name} isRequired maxLength={64} />
					<RadioGroupField name="scope" label={t.apiKeys.scope} options={scopes} />
					{create.error ? (
						<Notice tone="danger" role="alert">
							{errorMessage(create.error)}
						</Notice>
					) : null}
					<SubmitButton>{t.apiKeys.submit}</SubmitButton>
				</FormRoot>
			)}
		</Modal>
	);
}
