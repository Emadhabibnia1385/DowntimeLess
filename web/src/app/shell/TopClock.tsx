import { useEffect, useState } from "react";
import { formatClock } from "@/strings";

const zone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

// The device's own clock and zone, ticking each second, in the middle of the desktop top bar.
export function TopClock() {
	const [now, setNow] = useState(() => new Date());
	useEffect(() => {
		const tick = () => setNow(new Date());
		const timer = setInterval(tick, 1000);
		document.addEventListener("visibilitychange", tick);
		return () => {
			clearInterval(timer);
			document.removeEventListener("visibilitychange", tick);
		};
	}, []);
	const { weekday, time, gregorian, jalali } = formatClock(now);
	return (
		<time
			dir="ltr"
			dateTime={now.toISOString()}
			title={zone()}
			className="hidden tabular-nums lg:absolute lg:inset-x-0 lg:top-1/2 lg:mx-auto lg:flex lg:w-fit lg:-translate-y-1/2 lg:flex-col lg:items-center lg:leading-tight"
		>
			<span className="text-lg font-bold">
				{weekday} {time}
			</span>
			<span className="text-sm text-muted">
				{gregorian} · {jalali}
			</span>
		</time>
	);
}
