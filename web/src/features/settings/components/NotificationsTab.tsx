import { zodResolver } from "@hookform/resolvers/zod";
import {
	FormRoot,
	NumberField,
	Notice,
	SelectField,
	StaticTable,
	SubmitButton,
	SwitchField,
	toast,
} from "@nyxon/nasim";
import { type Resolver, useForm } from "react-hook-form";
import { z } from "zod";
import type { ChannelOut } from "@/api/generated/model";
import { useSettingsGet, useSettingsPut } from "@/api/generated/settings/settings";
import {
	useTelegramGetRoutes,
	useTelegramListChannels,
	useTelegramPutRoutes,
} from "@/api/generated/telegram/telegram";
import { errorMessage } from "@/api/transport";
import { useCanManage } from "@/features/auth";
import { Loadable } from "@/shared/Loadable";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";
import {
	DEFAULT_SETTINGS,
	onKey,
	QUOTA_BASIS,
	RULE_GROUPS,
	RULES,
	type Rule,
	type RuleUnit,
	UNIT_MAX,
} from "../lib/rules";
import { PANEL_ROUTE, routeKey, routeOptions, toRoutes } from "../lib/routes";
import { ChannelsCard } from "./ChannelsCard";

type Values = Record<string, number | boolean | string>;

const RULE_TEXT: Record<
	string,
	{ title: string; hint: string; warnNote?: string; critNote?: string }
> = t.notifications.rules;

const range = (unit: RuleUnit) => ({ max: UNIT_MAX[unit], message: t.notifications.range(unit) });

// One number per level, one switch per alert; a pair must stay in order (critical beyond warning).
const shape: Record<string, z.ZodType<number | boolean | string>> = { [QUOTA_BASIS]: z.boolean() };
for (const rule of RULES) {
	shape[onKey(rule.id)] = z.boolean();
	shape[routeKey(rule.id)] = z.string();
	for (const key of [rule.warn, rule.crit]) {
		if (key && rule.unit) {
			const { max, message } = range(rule.unit);
			shape[key] = z
				.number({ error: message })
				.min(1, { error: message })
				.max(max, { error: message });
		}
	}
}
const schema = z.object(shape).superRefine((values, context) => {
	for (const rule of RULES) {
		if (!rule.warn || !rule.crit || rule.unordered) continue;
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

function toValues(settings: Record<string, number>, routes: Record<string, string>): Values {
	const merged = { ...DEFAULT_SETTINGS, ...settings };
	return {
		...Object.fromEntries(
			Object.entries(merged).map(([key, value]) => [
				key,
				key.startsWith("on_") || key === QUOTA_BASIS ? value !== 0 : value,
			]),
		),
		...Object.fromEntries(RULES.map((rule) => [routeKey(rule.id), routes[rule.id] ?? PANEL_ROUTE])),
	};
}

function Level({
	name,
	label,
	unit,
	note,
	isDisabled,
}: {
	name: string | undefined;
	label: string;
	unit: Rule["unit"];
	note?: string;
	isDisabled: boolean;
}) {
	if (!name || !unit) return <span className="text-muted">{t.notifications.noValue}</span>;
	return (
		<div className="flex flex-col gap-1">
			<div className="flex items-center gap-2">
				<NumberField
					name={name}
					label={<span className="sr-only">{label}</span>}
					hideSteppers
					minValue={1}
					maxValue={UNIT_MAX[unit]}
					isDisabled={isDisabled}
					className={unit === "count" ? "w-28" : "w-20"}
				/>
				<span className="text-sm text-muted">{t.notifications.unit[unit]}</span>
			</div>
			{note ? <span className="text-xs text-muted">{note}</span> : null}
		</div>
	);
}

// Every alert as a table row: on/off switch, warning and critical levels, and where it is sent.
export function NotificationsTab() {
	const canManage = useCanManage();
	const settings = useSettingsGet();
	const routes = useTelegramGetRoutes({ query: { enabled: canManage } });
	const channels = useTelegramListChannels({ query: { enabled: canManage } });
	return (
		<Loadable query={settings}>
			{(values) =>
				canManage ? (
					<Loadable query={routes}>
						{(map) => (
							<Loadable query={channels}>
								{(list) => <RulesTable values={toValues(values, map)} channels={list} />}
							</Loadable>
						)}
					</Loadable>
				) : (
					<RulesTable values={toValues(values, {})} channels={[]} />
				)
			}
		</Loadable>
	);
}

function RulesTable({ values, channels }: { values: Values; channels: readonly ChannelOut[] }) {
	const canManage = useCanManage();
	const refresh = useRefreshAll();
	const saveSettings = useSettingsPut();
	const saveRoutes = useTelegramPutRoutes();
	const form = useForm<Values>({
		resolver: zodResolver(schema) as Resolver<Values>,
		defaultValues: values,
	});
	const options = routeOptions(channels);
	const submit = async (data: Values) => {
		const levels = Object.entries(data).filter(([key]) => !key.startsWith("route_"));
		try {
			await saveSettings.mutateAsync({
				data: Object.fromEntries(levels.map(([key, value]) => [key, Number(value)])),
			});
			if (canManage) {
				// a channel deleted since the page loaded is already back on its default
				const known = new Set(options.map((option) => option.value));
				const wanted = Object.entries(toRoutes(data)).filter(([, route]) => known.has(route));
				await saveRoutes.mutateAsync({ data: Object.fromEntries(wanted) });
			}
			toast.success(t.common.saved);
			void refresh();
		} catch (error) {
			toast.danger(errorMessage(error));
		}
	};
	const failure = saveSettings.error ?? saveRoutes.error;
	return (
		<div className="flex flex-col gap-6">
			<FormRoot form={form} className="flex flex-col gap-4" onSubmit={submit}>
				<p className="text-sm leading-7 text-muted">{t.notifications.intro}</p>
				<StaticTable
					caption={t.notifications.tableLabel}
					className="min-w-[56rem]"
					columns={[
						t.notifications.colRule,
						t.notifications.colWarn,
						t.notifications.colCrit,
						t.notifications.colChannel,
						t.notifications.colEnabled,
					]}
					rows={RULE_GROUPS.flatMap((group) => [
						{
							id: `group-${group}`,
							cells: [
								<span key="group" className="text-sm font-bold text-accent-soft-foreground">
									{t.notifications.groups[group]}
								</span>,
								"",
								"",
								"",
								"",
							],
						},
						...RULES.filter((rule) => rule.group === group).map((rule) => {
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
										note={text?.warnNote}
										isDisabled={!canManage}
									/>,
									<Level
										key="crit"
										name={rule.crit}
										label={t.notifications.critOf(title)}
										unit={rule.unit}
										note={text?.critNote}
										isDisabled={!canManage}
									/>,
									canManage ? (
										<SelectField
											key="channel"
											name={routeKey(rule.id)}
											label={<span className="sr-only">{t.notifications.routeOf(title)}</span>}
											options={options}
											className="w-52"
										/>
									) : (
										<span key="channel" className="text-muted">
											{t.notifications.noValue}
										</span>
									),
									<SwitchField
										key="on"
										name={onKey(rule.id)}
										label={<span className="sr-only">{t.notifications.enabled(title)}</span>}
										isDisabled={!canManage}
									/>,
								],
							};
						}),
					])}
				/>
				<SwitchField
					name={QUOTA_BASIS}
					label={t.notifications.quotaBasis}
					description={t.notifications.quotaBasisHint}
					isDisabled={!canManage}
				/>
				{failure ? (
					<Notice tone="danger" role="alert">
						{errorMessage(failure)}
					</Notice>
				) : null}
				{canManage ? (
					<SubmitButton>{t.notifications.save}</SubmitButton>
				) : (
					<Notice tone="info">{t.notifications.viewOnly}</Notice>
				)}
			</FormRoot>
			{canManage ? <ChannelsCard channels={channels} /> : null}
		</div>
	);
}
