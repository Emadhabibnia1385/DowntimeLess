import { zodResolver } from "@hookform/resolvers/zod";
import { FormRoot, Modal, Notice, NumberField, SubmitButton, TextField, toast } from "@nyxon/nasim";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useSslAddDomain } from "@/api/generated/ssl/ssl";
import { errorMessage } from "@/api/transport";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";

const DEFAULT_PORT = 443;

const schema = z.object({
	host: z
		.string()
		.trim()
		.min(1, { error: t.ssl.hostRequired })
		.min(3, { error: t.ssl.hostInvalid })
		.max(253, { error: t.ssl.hostInvalid })
		.regex(/^[A-Za-z0-9.-]+$/, { error: t.ssl.hostInvalid }),
	port: z
		.number({ error: t.ssl.portRange })
		.int({ error: t.ssl.portRange })
		.min(1, { error: t.ssl.portRange })
		.max(65_535, { error: t.ssl.portRange }),
	note: z.string().trim().max(120),
});
type Values = z.input<typeof schema>;

const EMPTY: Values = { host: "", port: DEFAULT_PORT, note: "" };

// The master probes the domain once when it is added, so the answer already carries the result.
export function AddDomainDialog({
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
	const add = useSslAddDomain({
		mutation: {
			onSuccess: () => {
				toast.success(t.ssl.added);
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
		<Modal isOpen={isOpen} onOpenChange={change} title={t.ssl.addTitle}>
			<FormRoot
				form={form}
				className="flex flex-col gap-4"
				onSubmit={(values) => add.mutate({ data: values })}
			>
				<p className="text-sm text-muted">{t.ssl.addHint}</p>
				<TextField
					name="host"
					label={t.ssl.host}
					description={t.ssl.hostHint}
					dir="ltr"
					isRequired
					maxLength={253}
					autoComplete="off"
					spellCheck={false}
				/>
				<NumberField
					name="port"
					label={t.ssl.port}
					minValue={1}
					maxValue={65_535}
					formatOptions={{ useGrouping: false }}
					hideSteppers
				/>
				<TextField name="note" label={t.ssl.note} maxLength={120} />
				{add.error ? (
					<Notice tone="danger" role="alert">
						{errorMessage(add.error)}
					</Notice>
				) : null}
				<SubmitButton>{t.ssl.submit}</SubmitButton>
			</FormRoot>
		</Modal>
	);
}
