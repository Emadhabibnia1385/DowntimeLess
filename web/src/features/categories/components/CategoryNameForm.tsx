import { zodResolver } from "@hookform/resolvers/zod";
import { FormRoot, Notice, SubmitButton, TextField } from "@nyxon/nasim";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { errorMessage } from "@/api/transport";
import { t } from "@/strings";

const schema = z.object({
	name: z
		.string()
		.trim()
		.min(1, { error: t.categories.nameRequired })
		.max(40, { error: t.categories.nameTooLong }),
});
type Values = z.output<typeof schema>;

// One field: the name of a category, for adding one and for renaming one.
export function CategoryNameForm({
	name,
	submitLabel,
	error,
	onSubmit,
}: {
	name: string;
	submitLabel: string;
	error: unknown;
	onSubmit: (name: string) => void;
}) {
	const form = useForm<z.input<typeof schema>, unknown, Values>({
		resolver: zodResolver(schema),
		defaultValues: { name },
	});
	return (
		<FormRoot
			form={form}
			onSubmit={(values) => {
				onSubmit(values.name);
				if (!name) form.reset({ name: "" });
			}}
			className="flex flex-col gap-3"
		>
			<TextField name="name" label={t.categories.name} isRequired maxLength={40} />
			{error ? (
				<Notice tone="danger" role="alert">
					{errorMessage(error)}
				</Notice>
			) : null}
			<SubmitButton>{submitLabel}</SubmitButton>
		</FormRoot>
	);
}
