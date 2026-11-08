import { useEffect, useState } from "react";
import { formatDateTime } from "@/strings/format";

// The date and time in the top bar, like the reference; a minute is as fine as it needs to be.
export function TopClock() {
	const [now, setNow] = useState(() => Date.now());
	useEffect(() => {
		const timer = setInterval(() => setNow(Date.now()), 30_000);
		return () => clearInterval(timer);
	}, []);
	return <span className="hidden text-sm text-muted sm:inline">{formatDateTime(now / 1000)}</span>;
}
