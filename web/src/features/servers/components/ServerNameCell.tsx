import { Link } from "@tanstack/react-router";
import type { ServerOut } from "@/api/generated/model";
import { IpText } from "@/shared/IpText";
import { ipv4Of } from "@/strings";
import { displayName } from "../lib/status";
import { whereOf } from "../lib/where";

// Flag and name (a link) side by side, then the IPv4 and the place under it.
export function ServerNameCell({ server }: { server: ServerOut }) {
	const { flag, place } = whereOf(server);
	const ip = ipv4Of(server.public_ip);
	return (
		<div className="min-w-0 text-center">
			<div className="flex items-center justify-center gap-1.5">
				<span aria-hidden className="text-xl leading-none">
					{flag}
				</span>
				<Link
					to="/servers/$serverId"
					params={{ serverId: String(server.id) }}
					className="font-semibold text-accent-soft-foreground underline-offset-4 hover:underline"
				>
					{displayName(server)}
				</Link>
			</div>
			{ip ? (
				<div>
					<IpText ip={ip} className="text-xs text-muted" />
				</div>
			) : null}
			{place ? (
				<p dir="ltr" className="text-xs text-muted">
					{place}
				</p>
			) : null}
		</div>
	);
}
