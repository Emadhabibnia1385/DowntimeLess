import { zodResolver } from "@hookform/resolvers/zod";
import { FormRoot, NumberField, Notice, SubmitButton, toast } from "@nyxon/nasim";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useSettingsPut } from "@/api/generated/settings/settings";
import { errorMessage } from "@/api/transport";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";
import { DEFAULT_THRESHOLDS } from "../api";

const KEYS = Object.keys(DEFAULT_THRESHOLDS);

const schema = z.record(
	z.string(),
	z
		.number({ error: t.settings.range })
		.min(1, { error: t.settings.range })
		.max(100, { error: t.settings.range }),
);
type Values = z.infer<typeof schema>;

const LABELS: Record<string, string> = t.settings.keys;

// One number field per threshold, all percentages; the master ignores keys it does not know.
export function ThresholdsForm({
	values,
	canManage,
}: {
	values: Record<string, number>;
	canManage: boolean;
}) {
	const refresh = useRefreshAll();
	const save = useSettingsPut({
		mutation: {
			onSuccess: () => {
				toast.success(t.common.saved);
				void refresh();
			},
			onError: (error) => toast.danger(errorMessage(error)),
		},
	});
	const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: values });
	return (
		<FormRoot
			form={form}
			onSubmit={(data) => save.mutate({ data })}
			className="flex flex-col gap-4"
		>
			<div className="grid gap-4 md:grid-cols-2">
				{KEYS.map((key) => (
					<NumberField
						key={key}
						name={key}
						label={LABELS[key] ?? key}
						description={t.settings.percentHint}
						minValue={1}
						maxValue={100}
						isDisabled={!canManage}
					/>
				))}
			</div>
			{save.error ? (
				<Notice tone="danger" role="alert">
					{errorMessage(save.error)}
				</Notice>
			) : null}
			{canManage ? <SubmitButton>{t.common.save}</SubmitButton> : null}
		</FormRoot>
	);
}
