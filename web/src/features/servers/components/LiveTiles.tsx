import { Notice, StatCard } from "@nyxon/nasim";
import type { ServerOut } from "@/api/generated/model";
import { formatBitRate, formatPercent, t } from "@/strings";

const pct = (value: number | null | undefined) =>
	value == null ? t.common.none : formatPercent(value);
const rate = (value: number | null | undefined) =>
	value == null ? t.common.none : formatBitRate(value);

// The latest report as tiles; the agent reports network rates in bits per second.
export function LiveTiles({ server }: { server: ServerOut }) {
	const { latest } = server;
	const failedUnits = latest.failed_units ?? [];
	return (
		<section aria-label={t.server.live} className="flex flex-col gap-3">
			{latest.reboot_required ? <Notice tone="warning">{t.server.rebootRequired}</Notice> : null}
			{failedUnits.length > 0 ? (
				<Notice tone="danger">
					{t.server.failedUnits}: <span dir="ltr">{failedUnits.join(", ")}</span>
				</Notice>
			) : null}
			<div className="grid grid-cols-2 gap-3 md:grid-cols-4">
				<StatCard label={t.server.liveCpu} value={pct(latest.cpu_pct)} />
				<StatCard label={t.server.liveRam} value={pct(latest.ram_pct)} />
				<StatCard label={t.server.liveDisk} value={pct(latest.disk_pct)} />
				<StatCard label={t.server.liveSteal} value={pct(latest.steal_pct)} />
				<StatCard label={t.server.liveRetrans} value={pct(latest.tcp_retrans_pct)} />
				<StatCard label={t.server.liveConntrack} value={pct(latest.conntrack_pct)} />
				<StatCard label={t.server.liveRx} value={rate(latest.rx_bps)} />
				<StatCard label={t.server.liveTx} value={rate(latest.tx_bps)} />
			</div>
		</section>
	);
}
