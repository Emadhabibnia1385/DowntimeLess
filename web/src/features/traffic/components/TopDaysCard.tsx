import { EmptyState, SectionCard, StaticTable } from "@nyxon/nasim";
import type { TopDay } from "@/api/generated/model";
import { formatBytes, formatDate, t } from "@/strings";

// The busiest days of the period, biggest first, with the Jalali date.
export function TopDaysCard({ days }: { days: readonly TopDay[] }) {
	return (
		<SectionCard title={t.traffic.topDays.title}>
			{days.length === 0 ? (
				<EmptyState title={t.traffic.topDays.empty} />
			) : (
				<StaticTable
					className="min-w-[24rem] [&_td]:whitespace-nowrap [&_th]:whitespace-nowrap"
					caption={t.traffic.topDays.tableLabel}
					columns={[t.traffic.topDays.day, t.traffic.download, t.traffic.upload, t.traffic.total]}
					rows={days.map((day) => ({
						id: day.date,
						cells: [
							formatDate(day.ts, "Asia/Tehran"),
							formatBytes(day.rx),
							formatBytes(day.tx),
							<strong key="total">{formatBytes(day.total)}</strong>,
						],
					}))}
				/>
			)}
		</SectionCard>
	);
}
