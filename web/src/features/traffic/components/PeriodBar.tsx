import { DateTimeField, SelectField } from "@nyxon/nasim";
import { useCategories } from "@/features/categories";
import { t } from "@/strings";
import { defaultCustom, isPeriodId, PERIOD_IDS, type Period } from "../lib/period";

const periodOptions = PERIOD_IDS.map((id) => ({ value: id, label: t.traffic.periods[id] }));

const ALL = "all";
const NONE = "none";
const dateOf = (value: string) => (value ? value.slice(0, 10) : undefined);
const fieldValue = (day: string | undefined) => (day ? `${day}T00:00` : "");

// The reporting period and, optionally, one server; a custom period adds two Jalali date fields.
export function PeriodBar({
	period,
	onPeriodChange,
	serverId,
	onServerChange,
	servers,
	category,
	onCategoryChange,
	nowSeconds,
}: {
	period: Period;
	onPeriodChange: (period: Period) => void;
	serverId: number | null;
	onServerChange: (serverId: number | null) => void;
	servers: { value: string; label: string }[];
	category: string | null;
	onCategoryChange: (category: string | null) => void;
	nowSeconds: number;
}) {
	const categories = useCategories();
	const categoryOptions = [
		{ value: ALL, label: t.categories.filterAll },
		...(categories.data ?? []).map((item) => ({ value: String(item.id), label: item.name })),
		{ value: NONE, label: t.categories.none },
	];
	const hasCategories = (categories.data ?? []).length > 0;
	const custom = period.id === "custom";
	const dateLabels = {
		calendarLabel: t.traffic.calendar,
		timeLabel: t.traffic.time,
		clearLabel: t.traffic.clear,
	};
	return (
		<div className="flex flex-col gap-2">
			<div
				className={`grid gap-3 sm:grid-cols-2 ${hasCategories ? "max-w-3xl lg:grid-cols-3" : "max-w-xl"}`}
			>
				<SelectField
					label={t.traffic.periodField}
					value={period.id}
					onChange={(next) => {
						if (!isPeriodId(next)) return;
						onPeriodChange(
							next === "custom"
								? { ...defaultCustom(nowSeconds), ...(period.id === "custom" ? period : {}) }
								: { id: next },
						);
					}}
					options={periodOptions}
				/>
				{hasCategories ? (
					<SelectField
						label={t.traffic.categoryField}
						value={category ?? ALL}
						onChange={(next) => onCategoryChange(next && next !== ALL ? next : null)}
						options={categoryOptions}
					/>
				) : null}
				<SelectField
					label={t.traffic.serverField}
					value={serverId === null ? ALL : String(serverId)}
					onChange={(next) => onServerChange(next && next !== ALL ? Number(next) : null)}
					options={[{ value: ALL, label: t.traffic.fleet }, ...servers]}
				/>
			</div>
			{custom ? (
				<>
					<div className="grid max-w-2xl gap-3 sm:grid-cols-2">
						<DateTimeField
							label={t.traffic.from}
							value={fieldValue(period.from)}
							onChange={(next) => onPeriodChange({ ...period, from: dateOf(next) })}
							{...dateLabels}
						/>
						<DateTimeField
							label={t.traffic.to}
							value={fieldValue(period.to)}
							onChange={(next) => onPeriodChange({ ...period, to: dateOf(next) })}
							{...dateLabels}
						/>
					</div>
					<p className="text-xs text-muted">{t.traffic.customHint}</p>
				</>
			) : null}
		</div>
	);
}
