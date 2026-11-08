import { ArrowDownIcon, ArrowUpIcon } from "@/shared/icons";
import { formatBytes, t } from "@/strings";

// Download and upload side by side, each with its arrow and a word for a screen reader.
export function Split({ rx, tx, className }: { rx: number; tx: number; className?: string }) {
	return (
		<span className={`inline-flex flex-wrap items-center gap-x-3 gap-y-0.5 ${className ?? ""}`}>
			<span className="inline-flex items-center gap-0.5 whitespace-nowrap">
				<ArrowDownIcon aria-hidden className="size-3.5 shrink-0" />
				<span className="sr-only">{t.traffic.download} </span>
				{formatBytes(rx)}
			</span>
			<span className="inline-flex items-center gap-0.5 whitespace-nowrap">
				<ArrowUpIcon aria-hidden className="size-3.5 shrink-0" />
				<span className="sr-only">{t.traffic.upload} </span>
				{formatBytes(tx)}
			</span>
		</span>
	);
}
