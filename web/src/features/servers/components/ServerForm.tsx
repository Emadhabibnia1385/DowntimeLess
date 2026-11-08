import { zodResolver } from "@hookform/resolvers/zod";
import { FormRoot, Notice, SelectField, SubmitButton, TextField } from "@nyxon/nasim";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { errorMessage } from "@/api/transport";
import { useCategories } from "@/features/categories";
import { NO_CATEGORY } from "../lib/category";
import { t } from "@/strings";

const ROLES = ["exit", "relay", "panel", "panel_only", "other"] as const;

const schema = z.object({
	name: z
		.string()
		.trim()
		.min(1, { error: t.servers.nameRequired })
		.max(64, { error: t.servers.nameTooLong }),
	alias: z.string().trim().max(64, { error: t.servers.nameTooLong }),
	role: z.enum(ROLES),
	category: z.string(),
});
export type ServerFormValues = z.output<typeof schema>;

const roleOptions = ROLES.map((role) => ({ value: role, label: t.roles[role] }));

// The fields shared by adding a server and editing one: name, alias, category, role.
export function ServerForm({
	defaults,
	submitLabel,
	error,
	onSubmit,
}: {
	defaults: ServerFormValues;
	submitLabel: string;
	error: unknown;
	onSubmit: (values: ServerFormValues) => void;
}) {
	const categories = useCategories();
	const categoryOptions = [
		{ value: NO_CATEGORY, label: t.categories.none },
		...(categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name })),
	];
	const form = useForm<z.input<typeof schema>, unknown, ServerFormValues>({
		resolver: zodResolver(schema),
		defaultValues: defaults,
	});
	return (
		<FormRoot form={form} onSubmit={onSubmit} className="flex flex-col gap-4">
			<TextField name="name" label={t.servers.name} isRequired maxLength={64} />
			<TextField name="alias" label={t.servers.alias} maxLength={64} />
			<SelectField name="category" label={t.categories.field} options={categoryOptions} />
			<SelectField name="role" label={t.servers.role} options={roleOptions} />
			{error ? (
				<Notice tone="danger" role="alert">
					{errorMessage(error)}
				</Notice>
			) : null}
			<SubmitButton>{submitLabel}</SubmitButton>
		</FormRoot>
	);
}
