import { FormRoot, Modal, Notice, SelectField, SubmitButton, TextField } from "@nyxon/nasim";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import type { JobCreate } from "@/api/generated/model";
import { t } from "@/strings";
import { useQueueJobs, useServers } from "../api";

export type ToolKind = "traceroute" | "dns_check" | "http_check" | "journal" | "service_restart";

const HOST = /^[A-Za-z0-9:][A-Za-z0-9.:_-]{0,252}$/;
const UNIT = /^[A-Za-z0-9@._:-]{1,100}$/;
const LINES = ["50", "100", "200", "300"];

const schema = z.object({
	target: z.string().trim(),
	url: z.string().trim(),
	unit: z.string().trim(),
	lines: z.string(),
});
type Values = z.input<typeof schema>;

// Checks each field only for the kinds that use it, so a hidden field never blocks the form.
function problems(kind: ToolKind, values: Values): Partial<Record<keyof Values, string>> {
	const out: Partial<Record<keyof Values, string>> = {};
	if ((kind === "traceroute" || kind === "dns_check") && !HOST.test(values.target)) {
		out.target = values.target === "" ? t.server.pingRequired : t.server.toolHostInvalid;
	}
	if (kind === "http_check" && !/^https?:\/\/\S{1,2000}$/.test(values.url)) {
		out.url = t.server.toolUrlInvalid;
	}
	if (kind === "service_restart" && !UNIT.test(values.unit)) {
		out.unit = values.unit === "" ? t.server.toolUnitRequired : t.server.toolUnitInvalid;
	}
	if (kind === "journal" && values.unit !== "" && !UNIT.test(values.unit)) {
		out.unit = t.server.toolUnitInvalid;
	}
	return out;
}

function jobOf(kind: ToolKind, values: Values): JobCreate {
	switch (kind) {
		case "traceroute":
		case "dns_check":
			return { kind, args: { target: values.target } };
		case "http_check":
			return { kind, args: { url: values.url } };
		case "service_restart":
			return { kind, args: { unit: values.unit } };
		case "journal":
			return {
				kind,
				args:
					values.unit === ""
						? { lines: Number(values.lines) }
						: { unit: values.unit, lines: Number(values.lines) },
			};
	}
}

// One dialog for tools that need a typed value: a host, an address, a service name or a line count.
export function ToolDialog({
	serverId,
	kind,
	isOpen,
	onOpenChange,
}: {
	serverId: number;
	kind: ToolKind;
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const servers = useServers();
	const queue = useQueueJobs(serverId, () => onOpenChange(false));
	const form = useForm<Values>({
		resolver: async (values) => {
			const parsed = schema.safeParse(values);
			if (!parsed.success) return { values: {}, errors: {} };
			const found = problems(kind, parsed.data);
			const keys = Object.keys(found) as (keyof Values)[];
			if (keys.length === 0) return { values: parsed.data, errors: {} };
			return {
				values: {},
				errors: Object.fromEntries(
					keys.map((key) => [key, { type: "validate", message: found[key] }]),
				),
			};
		},
		defaultValues: { target: "", url: "", unit: "", lines: "100" },
	});
	const target = useWatch({ control: form.control, name: "target" });
	const options = (servers.data ?? [])
		.filter((server) => server.id !== serverId && server.public_ip)
		.map((server) => ({
			value: server.public_ip ?? "",
			label: `${server.alias || server.name} (${server.public_ip})`,
		}));
	const hostKind = kind === "traceroute" || kind === "dns_check";
	return (
		<Modal
			isOpen={isOpen}
			onOpenChange={onOpenChange}
			title={(t.server.jobKinds as Record<string, string>)[kind] ?? kind}
			isBusy={queue.isPending}
		>
			<FormRoot
				form={form}
				className="flex flex-col gap-4"
				onSubmit={(values) => queue.mutate([jobOf(kind, values)])}
			>
				{kind === "service_restart" ? (
					<Notice tone="warning">{t.server.toolRestartWarn}</Notice>
				) : null}
				{hostKind ? (
					<>
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
					</>
				) : null}
				{kind === "http_check" ? (
					<TextField
						name="url"
						dir="ltr"
						label={t.server.toolUrl}
						description={t.server.toolUrlHint}
						spellCheck={false}
						isRequired
					/>
				) : null}
				{kind === "service_restart" || kind === "journal" ? (
					<TextField
						name="unit"
						dir="ltr"
						label={t.server.toolUnit}
						description={kind === "journal" ? t.server.toolUnitOptional : t.server.toolUnitHint}
						spellCheck={false}
						isRequired={kind === "service_restart"}
					/>
				) : null}
				{kind === "journal" ? (
					<SelectField
						name="lines"
						label={t.server.toolLines}
						options={LINES.map((value) => ({ value, label: value }))}
					/>
				) : null}
				<SubmitButton>{t.server.toolRun}</SubmitButton>
			</FormRoot>
		</Modal>
	);
}
