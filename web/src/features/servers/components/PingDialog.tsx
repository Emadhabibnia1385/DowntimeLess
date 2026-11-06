import { zodResolver } from "@hookform/resolvers/zod";
import { FormRoot, Modal, SelectField, SubmitButton, TextField } from "@nyxon/nasim";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { t } from "@/strings";
import { useQueueJobs, useServers } from "../api";

const schema = z.object({ target: z.string().trim().min(1, { error: t.server.pingRequired }) });
type Values = z.input<typeof schema>;

// Ping from this server to a host typed in, or to another server of the fleet picked from the list.
export function PingDialog({
	serverId,
	isOpen,
	onOpenChange,
}: {
	serverId: number;
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const servers = useServers();
	const queue = useQueueJobs(serverId, () => onOpenChange(false));
	const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { target: "" } });
	const target = useWatch({ control: form.control, name: "target" });
	const options = (servers.data ?? [])
		.filter((server) => server.id !== serverId && server.public_ip)
		.map((server) => ({
			value: server.public_ip ?? "",
			label: `${server.alias || server.name} (${server.public_ip})`,
		}));
	return (
		<Modal
			isOpen={isOpen}
			onOpenChange={onOpenChange}
			title={t.server.pingTitle}
			isBusy={queue.isPending}
		>
			<FormRoot
				form={form}
				className="flex flex-col gap-4"
				onSubmit={(values) =>
					queue.mutate([{ kind: "ping", args: { target: values.target.trim() } }])
				}
			>
				<TextField
					name="target"
					dir="ltr"
					label={t.server.pingTarget}
					description={t.server.pingTargetHint}
					spellCheck={false}
					isRequired
				/>
				{options.length > 0 ? (
					<SelectField
						label={t.server.pingPick}
						options={options}
						value={options.some((option) => option.value === target) ? target : null}
						onChange={(value) => form.setValue("target", value ?? "", { shouldValidate: true })}
					/>
				) : null}
				<SubmitButton>{t.server.pingStart}</SubmitButton>
			</FormRoot>
		</Modal>
	);
}
