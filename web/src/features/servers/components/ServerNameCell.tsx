import { Link } from "@tanstack/react-router";
import type { ServerOut } from "@/api/generated/model";
import { IpText } from "@/shared/IpText";
import { ipv4Of } from "@/strings";
import { displayName } from "../lib/status";
import { whereOf } from "../lib/where";

// Country and city on one line, the provider on the next, so a long place never widens the table.
function placeLines(place: string): string[] {
	const parts = place.split(" · ");
	return parts.length >= 3 ? [parts.slice(0, 2).join(" · "), parts.slice(2).join(" · ")] : [place];
}

// Flag and name (a link) side by side, then the IPv4 and the place under it.
export function ServerNameCell({ server }: { server: ServerOut }) {
	const { flag, place } = whereOf(server);
	const ip = ipv4Of(server.public_ip);
	return (
		<div className="mx-auto min-w-0 max-w-64 text-center">
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
				<p dir="ltr" className="mx-auto max-w-56 text-pretty break-words text-xs text-muted">
					{placeLines(place).map((line) => (
						<span key={line} className="block">
							{line}
						</span>
					))}
				</p>
			) : null}
		</div>
	);
}
