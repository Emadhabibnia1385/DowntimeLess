import { zodResolver } from "@hookform/resolvers/zod";
import { FormRoot, Notice, SelectField, SubmitButton, TextAreaField, toast } from "@nyxon/nasim";
import { useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useReportsAddChange } from "@/api/generated/reports/reports";
import { errorMessage } from "@/api/transport";
import { useCanManage } from "@/features/auth/session";
import { useServers } from "@/features/servers";
import { t } from "@/strings";

const N = t.issueChanges.note;
const NO_SERVER = "none";
const MAX = 500;

const schema = z.object({
	text: z.string().trim().min(1, { error: N.textRequired }).max(MAX, { error: N.textTooLong }),
	server: z.string().optional(),
});
type Values = z.input<typeof schema>;
const EMPTY: Values = { text: "", server: NO_SERVER };

// Admins and the owner write notes; the master enforces the same rank.
export function NoteForm() {
	const allowed = useCanManage();
	const servers = useServers();
	const queryClient = useQueryClient();
	const form = useForm<Values, unknown, z.output<typeof schema>>({
		resolver: zodResolver(schema),
		defaultValues: EMPTY,
	});
	const add = useReportsAddChange({
		mutation: {
			onSuccess: () => {
				toast.success(N.saved);
				form.reset(EMPTY);
				void queryClient.invalidateQueries({ queryKey: ["reports", "changes"] });
			},
		},
	});
	if (!allowed) return null;
	const options = [
		{ value: NO_SERVER, label: N.noServer },
		...(servers.data ?? []).map((s) => ({ value: String(s.id), label: s.alias || s.name })),
	];
	return (
		<FormRoot
			form={form}
			className="flex max-w-xl flex-col gap-3 rounded-xl border border-border p-4"
			aria-label={N.title}
			onSubmit={(values) =>
				add.mutate({
					data: {
						text: values.text,
						server_id: values.server && values.server !== NO_SERVER ? Number(values.server) : null,
					},
				})
			}
		>
			<h3 className="font-semibold">{N.title}</h3>
			<p className="text-sm text-muted">{N.hint}</p>
			<TextAreaField name="text" label={N.text} isRequired maxLength={MAX} rows={2} />
			<SelectField name="server" label={N.server} options={options} />
			{add.error ? (
				<Notice tone="danger" role="alert">
					{errorMessage(add.error)}
				</Notice>
			) : null}
			<SubmitButton>{N.submit}</SubmitButton>
		</FormRoot>
	);
}
