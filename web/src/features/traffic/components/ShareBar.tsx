import { formatPercent } from "@/strings";

// A server's part of the fleet's traffic: the figure and a small bar made of tokens.
export function ShareBar({ percent }: { percent: number }) {
	return (
		<div className="flex min-w-16 flex-col items-center gap-1">
			<span className="tabular-nums">{formatPercent(percent)}</span>
			<div aria-hidden className="h-1.5 w-full rounded-full bg-surface-tertiary">
				<div
					className="h-1.5 rounded-full bg-accent"
					style={{ width: `${Math.min(100, Math.max(percent > 0 ? 2 : 0, percent))}%` }}
				/>
			</div>
		</div>
	);
}
