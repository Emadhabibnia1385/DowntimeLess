import { CopyButton } from "@nyxon/nasim";
import { t } from "@/strings";

// An IP address with a small icon button after it that copies it; the icon turns into a tick.
export function IpText({ ip, className = "" }: { ip: string; className?: string }) {
	return (
		<span dir="ltr" className={`inline-flex items-center gap-1 ${className}`}>
			<span className="font-mono">{ip}</span>
			<CopyButton
				value={ip}
				label={t.common.copyIp}
				doneLabel=""
				variant="ghost"
				className="size-6 min-h-0 min-w-0 gap-0 p-0 text-[0px] [&_svg]:size-4"
			/>
		</span>
	);
}
