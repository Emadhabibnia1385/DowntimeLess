import { zodResolver } from "@hookform/resolvers/zod";
import {
	FormRoot,
	Modal,
	Notice,
	RadioGroupField,
	SubmitButton,
	TextAreaField,
	toast,
} from "@nyxon/nasim";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { useIssuesAck } from "@/api/generated/issues/issues";
import { errorMessage } from "@/api/transport";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";
import { type AckValues, ackSchema, MODE_OPTIONS, NOTE_MAX } from "./lib";

const EMPTY: AckValues = { mode: "until_resolved", note: "" };

export type AckTarget = { key: string; title: string; server: string };

// The master checks that the key is a current issue here and that the caller may acknowledge it.
export function AckDialog({ target, onClose }: { target: AckTarget | null; onClose: () => void }) {
	const refresh = useRefreshAll();
	const form = useForm<AckValues, unknown, z.output<typeof ackSchema>>({
		resolver: zodResolver(ackSchema),
		defaultValues: EMPTY,
	});
	const ack = useIssuesAck({
		mutation: {
			onSuccess: () => {
				toast.success(t.issueAcks.done);
				void refresh();
				change(false);
			},
		},
	});
	const change = (open: boolean) => {
		if (open) return;
		onClose();
		ack.reset();
		form.reset(EMPTY);
	};
	return (
		<Modal isOpen={target !== null} onOpenChange={change} title={t.issueAcks.title}>
			<FormRoot
				form={form}
				className="flex flex-col gap-4"
				onSubmit={(values) =>
					target && ack.mutate({ data: { key: target.key, mode: values.mode, note: values.note } })
				}
			>
				{target ? (
					<p className="font-semibold">
						{target.title}
						{target.server ? (
							<span className="font-normal text-muted"> · {target.server}</span>
						) : null}
					</p>
				) : null}
				<p className="text-sm text-muted">{t.issueAcks.body}</p>
				<RadioGroupField name="mode" label={t.issueAcks.modeLabel} options={MODE_OPTIONS} />
				<TextAreaField
					name="note"
					label={t.issueAcks.note}
					description={t.issueAcks.noteHint}
					rows={2}
					maxLength={NOTE_MAX}
				/>
				{ack.error ? (
					<Notice tone="danger" role="alert">
						{errorMessage(ack.error)}
					</Notice>
				) : null}
				<SubmitButton>{t.issueAcks.submit}</SubmitButton>
			</FormRoot>
		</Modal>
	);
}
