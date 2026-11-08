import { zodResolver } from "@hookform/resolvers/zod";
import { FormRoot, Modal, SelectField, SubmitButton, TextField } from "@nyxon/nasim";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { t } from "@/strings";
import { useQueueJobs, useServers } from "../api";

const MAX_PORT = 65_535;
const validPort = (text: string) =>
	/^\d{1,5}$/.test(text) && Number(text) > 0 && Number(text) <= MAX_PORT;

const schemaFor = (withPort: boolean) =>
	z.object({
		target: z.string().trim().min(1, { error: t.server.pingRequired }),
		port: withPort
			? z.string().trim().refine(validPort, { error: t.server.tcpPortInvalid })
			: z.string(),
	});
type Values = z.input<ReturnType<typeof schemaFor>>;

// Ping or a TCP port check from this server to a host typed in, or to another server of the fleet.
export function CheckDialog({
	serverId,
	kind,
	isOpen,
	onOpenChange,
}: {
	serverId: number;
	kind: "ping" | "tcp_check";
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const servers = useServers();
	const queue = useQueueJobs(serverId, () => onOpenChange(false));
	const withPort = kind === "tcp_check";
	const form = useForm<Values>({
		resolver: zodResolver(schemaFor(withPort)),
		defaultValues: { target: "", port: "" },
	});
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
			title={withPort ? t.server.tcpTitle : t.server.pingTitle}
			isBusy={queue.isPending}
		>
			<FormRoot
				form={form}
				className="flex flex-col gap-4"
				onSubmit={(values) =>
					queue.mutate([
						{
							kind,
							args: withPort
								? { target: values.target.trim(), port: Number(values.port) }
								: { target: values.target.trim() },
						},
					])
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
				{withPort ? (
					<TextField
						name="port"
						dir="ltr"
						inputMode="numeric"
						label={t.server.tcpPort}
						isRequired
					/>
				) : null}
				<SubmitButton>{t.server.pingStart}</SubmitButton>
			</FormRoot>
		</Modal>
	);
}
