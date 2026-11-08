import { zodResolver } from "@hookform/resolvers/zod";
import {
	FormRoot,
	NumberField,
	Notice,
	StaticTable,
	StatusChip,
	SubmitButton,
	SwitchField,
	toast,
} from "@nyxon/nasim";
import { type Resolver, useForm } from "react-hook-form";
import { z } from "zod";
import { useSettingsGet, useSettingsPut } from "@/api/generated/settings/settings";
import { errorMessage } from "@/api/transport";
import { useCanManage } from "@/features/auth";
import { Loadable } from "@/shared/Loadable";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";
import { DEFAULT_SETTINGS, onKey, type Rule, RULES } from "../lib/rules";

type Values = Record<string, number | boolean>;

const RULE_TEXT: Record<string, { title: string; hint: string }> = t.notifications.rules;

const range = (rule: Rule) =>
	rule.unit === "days"
		? { max: 365, message: t.notifications.rangeDays }
		: { max: 100, message: t.notifications.rangePercent };

// One number per level, one switch per alert; a pair must stay in order (critical beyond warning).
const shape: Record<string, z.ZodType<number | boolean>> = {};
for (const rule of RULES) {
	shape[onKey(rule.id)] = z.boolean();
	const { max, message } = range(rule);
	for (const key of [rule.warn, rule.crit]) {
		if (key) {
			shape[key] = z
				.number({ error: message })
				.min(1, { error: message })
				.max(max, { error: message });
		}
	}
}
const schema = z.object(shape).superRefine((values, context) => {
	for (const rule of RULES) {
		if (!rule.warn || !rule.crit) continue;
		const warn = values[rule.warn] as number;
		const crit = values[rule.crit] as number;
		const ascending = rule.unit !== "days";
		if (ascending ? crit < warn : crit > warn) {
			context.addIssue({
				code: "custom",
				path: [rule.crit],
				message: ascending ? t.notifications.orderUp : t.notifications.orderDown,
			});
		}
	}
});

function toValues(settings: Record<string, number>): Values {
	const merged = { ...DEFAULT_SETTINGS, ...settings };
	return Object.fromEntries(
		Object.entries(merged).map(([key, value]) => [
			key,
			key.startsWith("on_") ? value !== 0 : value,
		]),
	);
}

function Level({
	name,
	label,
	unit,
	isDisabled,
}: {
	name: string | undefined;
	label: string;
	unit: Rule["unit"];
	isDisabled: boolean;
}) {
	if (!name) return <span className="text-muted">{t.notifications.noValue}</span>;
	return (
		<div className="flex items-center gap-2">
			<NumberField
				name={name}
				label={<span className="sr-only">{label}</span>}
				hideSteppers
				minValue={1}
				maxValue={unit === "days" ? 365 : 100}
				isDisabled={isDisabled}
				className="w-20"
			/>
			<span className="text-sm text-muted">
				{unit === "days" ? t.notifications.days : t.notifications.percent}
			</span>
		</div>
	);
}

// Every alert as a table row: on/off switch, warning and critical levels, and where it is sent.
export function NotificationsTab() {
	const settings = useSettingsGet();
	return (
		<Loadable query={settings}>{(values) => <RulesTable values={toValues(values)} />}</Loadable>
	);
}

function RulesTable({ values }: { values: Values }) {
	const canManage = useCanManage();
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
	const form = useForm<Values>({
		resolver: zodResolver(schema) as Resolver<Values>,
		defaultValues: values,
	});
	return (
		<FormRoot
			form={form}
			className="flex flex-col gap-4"
			onSubmit={(data) =>
				save.mutate({
					data: Object.fromEntries(
						Object.entries(data).map(([key, value]) => [key, Number(value)]),
					),
				})
			}
		>
			<p className="text-sm leading-7 text-muted">{t.notifications.intro}</p>
			<StaticTable
				caption={t.notifications.tableLabel}
				className="min-w-[44rem]"
				columns={[
					t.notifications.colRule,
					t.notifications.colWarn,
					t.notifications.colCrit,
					t.notifications.colChannel,
					t.notifications.colEnabled,
				]}
				rows={RULES.map((rule) => {
					const text = RULE_TEXT[rule.id];
					const title = text?.title ?? rule.id;
					return {
						id: rule.id,
						cells: [
							<div key="rule" className="flex flex-col gap-0.5">
								<span className="font-semibold">{title}</span>
								<span className="text-xs font-normal text-muted">{text?.hint}</span>
							</div>,
							<Level
								key="warn"
								name={rule.warn}
								label={t.notifications.warnOf(title)}
								unit={rule.unit}
								isDisabled={!canManage}
							/>,
							<Level
								key="crit"
								name={rule.crit}
								label={t.notifications.critOf(title)}
								unit={rule.unit}
								isDisabled={!canManage}
							/>,
							<StatusChip
								key="channel"
								tone={rule.telegram ? "info" : "neutral"}
								label={rule.telegram ? t.notifications.channelBoth : t.notifications.channelPanel}
								size="sm"
							/>,
							<SwitchField
								key="on"
								name={onKey(rule.id)}
								label={<span className="sr-only">{t.notifications.enabled(title)}</span>}
								isDisabled={!canManage}
							/>,
						],
					};
				})}
			/>
			{save.error ? (
				<Notice tone="danger" role="alert">
					{errorMessage(save.error)}
				</Notice>
			) : null}
			{canManage ? (
				<SubmitButton>{t.notifications.save}</SubmitButton>
			) : (
				<Notice tone="info">{t.notifications.viewOnly}</Notice>
			)}
		</FormRoot>
	);
}
