import { DateTimeField, SelectField } from "@nyxon/nasim";
import { t } from "@/strings";
import { defaultCustom, isPeriodId, PERIOD_IDS, type Period } from "../lib/period";

const periodOptions = PERIOD_IDS.map((id) => ({ value: id, label: t.traffic.periods[id] }));

const ALL = "all";
const dateOf = (value: string) => (value ? value.slice(0, 10) : undefined);
const fieldValue = (day: string | undefined) => (day ? `${day}T00:00` : "");

// The reporting period and, optionally, one server; a custom period adds two Jalali date fields.
export function PeriodBar({
	period,
	onPeriodChange,
	serverId,
	onServerChange,
	servers,
	nowSeconds,
}: {
	period: Period;
	onPeriodChange: (period: Period) => void;
	serverId: number | null;
	onServerChange: (serverId: number | null) => void;
	servers: { value: string; label: string }[];
	nowSeconds: number;
}) {
	const custom = period.id === "custom";
	const dateLabels = {
		calendarLabel: t.traffic.calendar,
		timeLabel: t.traffic.time,
		clearLabel: t.traffic.clear,
	};
	return (
		<div className="flex flex-col gap-2">
			<div className="grid max-w-xl gap-3 sm:grid-cols-2">
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
