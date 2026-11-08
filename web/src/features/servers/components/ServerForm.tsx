import { zodResolver } from "@hookform/resolvers/zod";
import { FormRoot, Notice, NumberField, SelectField, SubmitButton, TextField } from "@nyxon/nasim";
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
	quota_gb: z
		.number({ error: t.servers.quotaGbRange })
		.positive({ error: t.servers.quotaGbRange })
		.max(1_000_000, { error: t.servers.quotaGbRange })
		.optional(),
	quota_reset_day: z
		.number({ error: t.servers.quotaDayRange })
		.int({ error: t.servers.quotaDayRange })
		.min(1, { error: t.servers.quotaDayRange })
		.max(31, { error: t.servers.quotaDayRange })
		.optional(),
});
export type ServerFormValues = z.output<typeof schema>;

const roleOptions = ROLES.map((role) => ({ value: role, label: t.roles[role] }));

// Fields shared by add and edit; the quota only when editing (a new server has no history).
export function ServerForm({
	defaults,
	submitLabel,
	error,
	onSubmit,
	withQuota = false,
}: {
	defaults: ServerFormValues;
	submitLabel: string;
	error: unknown;
	onSubmit: (values: ServerFormValues) => void;
	withQuota?: boolean;
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
			{withQuota ? (
				<>
					<NumberField
						name="quota_gb"
						label={t.servers.quotaGb}
						description={t.servers.quotaGbHint}
						minValue={1}
						maxValue={1_000_000}
						formatOptions={{ useGrouping: false }}
						hideSteppers
					/>
					<NumberField
						name="quota_reset_day"
						label={t.servers.quotaResetDay}
						description={t.servers.quotaResetDayHint}
						minValue={1}
						maxValue={31}
						formatOptions={{ useGrouping: false }}
						hideSteppers
					/>
				</>
			) : null}
			{error ? (
				<Notice tone="danger" role="alert">
					{errorMessage(error)}
				</Notice>
			) : null}
			<SubmitButton>{submitLabel}</SubmitButton>
		</FormRoot>
	);
}
