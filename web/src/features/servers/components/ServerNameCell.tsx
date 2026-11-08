import { Link } from "@tanstack/react-router";
import type { ServerOut } from "@/api/generated/model";
import { flagOf, ipv4Of, placeLine } from "@/strings";
import { displayName } from "../lib/status";

// Flag and name (a link), then place and IPv4 under it.
export function ServerNameCell({ server }: { server: ServerOut }) {
	const place = placeLine(server);
	const ip = ipv4Of(server.public_ip);
	return (
		<div className="flex items-center gap-2">
			<span aria-hidden className="text-2xl leading-none">
				{flagOf(server.country)}
			</span>
			<div className="min-w-0 max-w-48">
				<Link
					to="/servers/$serverId"
					params={{ serverId: String(server.id) }}
					className="font-semibold text-accent-soft-foreground underline-offset-4 hover:underline"
				>
					{displayName(server)}
				</Link>
				{place ? (
					<p dir="ltr" className="text-start text-xs text-muted">
						{place}
					</p>
				) : null}
				{ip ? (
					<p dir="ltr" className="text-start font-mono text-xs text-muted">
						{ip}
					</p>
				) : null}
			</div>
		</div>
	);
}
