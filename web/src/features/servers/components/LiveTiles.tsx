import { Notice, StatCard } from "@nyxon/nasim";
import type { ReactNode } from "react";
import type { ServerOut } from "@/api/generated/model";
import { ArrowDownIcon, ArrowUpIcon } from "@/shared/icons";
import { formatDecimal, formatDuration, t } from "@/strings";
import { cpuUsage, diskUsage, ramUsage, type Usage } from "../lib/usage";

const MEGA = 1_000_000;
const TILE = "gap-1 p-3 sm:p-3";

const mbps = (bps: number | null | undefined) =>
	bps == null ? t.common.none : formatDecimal(bps / MEGA, bps < 10 * MEGA ? 2 : 1);

function Tile({ label, usage }: { label: string; usage: Usage | null }) {
	return (
		<StatCard
			className={TILE}
			label={label}
			value={usage?.percent ?? t.common.none}
			hint={usage?.detail}
		/>
	);
}

function Alerts({ latest }: { latest: ServerOut["latest"] }): ReactNode {
	const failedUnits = latest.failed_units ?? [];
	return (
		<>
			{latest.reboot_required ? <Notice tone="warning">{t.server.rebootRequired}</Notice> : null}
			{failedUnits.length > 0 ? (
				<Notice tone="danger">
					{t.server.failedUnits}: <span dir="ltr">{failedUnits.join(", ")}</span>
				</Notice>
			) : null}
		</>
	);
}

// The latest report as one row of small tiles; the agent reports network rates in bits per second.
export function LiveTiles({ server }: { server: ServerOut }) {
	const { latest } = server;
	const { load1, load5, load15, uptime_s: uptime } = latest;
	const uptimeParts = uptime == null ? [] : formatDuration(uptime).split(` ${t.units.and} `);
	const one = (value: number | null | undefined) =>
		value == null ? t.common.none : formatDecimal(value, 2);
	return (
		<section aria-label={t.server.live} className="flex flex-col gap-3">
			<Alerts latest={latest} />
			<div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-[repeat(3,minmax(0,1fr))_minmax(0,1.6fr)_repeat(3,minmax(0,1fr))]">
				<Tile label={t.server.liveCpu} usage={cpuUsage(latest)} />
				<Tile label={t.server.liveRam} usage={ramUsage(latest)} />
				<Tile label={t.server.liveDisk} usage={diskUsage(latest)} />
				<StatCard
					className={TILE}
					label={t.server.liveLoad}
					value={one(load1)}
					hint={t.server.liveLoadHint(one(load5), one(load15))}
				/>
				<StatCard
					className={TILE}
					label={t.server.liveRx}
					icon={<ArrowDownIcon />}
					value={mbps(latest.rx_bps)}
					hint={t.units.megabit}
				/>
				<StatCard
					className={TILE}
					label={t.server.liveTx}
					icon={<ArrowUpIcon />}
					value={mbps(latest.tx_bps)}
					hint={t.units.megabit}
				/>
				<StatCard
					className={TILE}
					label={t.server.liveUptime}
					value={uptimeParts[0] ?? t.common.none}
					hint={uptimeParts[1]}
				/>
			</div>
		</section>
	);
}
