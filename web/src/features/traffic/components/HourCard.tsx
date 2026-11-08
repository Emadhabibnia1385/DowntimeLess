import { ColumnChart, SectionCard } from "@nyxon/nasim";
import type { HourProfile } from "@/api/generated/model";
import { formatBytes, formatHour, t } from "@/strings";
import { busiestHour } from "../lib/chart";

// The average traffic of each hour of the day over the period: which hours are busy.
export function HourCard({ profile }: { profile: readonly HourProfile[] }) {
	const best = busiestHour(profile);
	return (
		<SectionCard title={t.traffic.hours.title} description={t.traffic.hours.description}>
			<ColumnChart
				title={t.traffic.hours.tableLabel}
				tone="accent"
				size="lg"
				showSummary
				summary={
					best
						? t.traffic.hours.summary(formatHour(best.hour), formatBytes(best.rx + best.tx))
						: t.traffic.hours.empty
				}
				empty={t.traffic.hours.empty}
				points={profile.map((entry) => ({
					key: String(entry.hour),
					label: formatHour(entry.hour),
					tooltip: t.traffic.hours.tooltip(
						formatHour(entry.hour),
						formatBytes(entry.rx),
						formatBytes(entry.tx),
					),
					value: entry.rx + entry.tx,
				}))}
				table={{
					showLabel: t.traffic.hours.showTable,
					label: t.traffic.hours.tableLabel,
					columns: [t.traffic.hours.hour, t.traffic.download, t.traffic.upload, t.traffic.total],
					rows: profile.map((entry) => ({
						key: String(entry.hour),
						cells: [
							formatHour(entry.hour),
							formatBytes(entry.rx),
							formatBytes(entry.tx),
							formatBytes(entry.rx + entry.tx),
						],
					})),
				}}
			/>
		</SectionCard>
	);
}
