import { Link } from "@tanstack/react-router";
import type { ServerOut } from "@/api/generated/model";
import { ipv4Of } from "@/strings";
import { displayName } from "../lib/status";
import { whereOf } from "../lib/where";

// Flag and name (a link), then the IPv4 and the place under it.
export function ServerNameCell({ server }: { server: ServerOut }) {
	const { flag, place } = whereOf(server);
	const ip = ipv4Of(server.public_ip);
	return (
		<div className="flex items-center justify-center gap-2">
			<span aria-hidden className="text-2xl leading-none">
				{flag}
			</span>
			<div className="min-w-0 max-w-44 text-center">
				<Link
					to="/servers/$serverId"
					params={{ serverId: String(server.id) }}
					className="font-semibold text-accent-soft-foreground underline-offset-4 hover:underline"
				>
					{displayName(server)}
				</Link>
				{ip ? (
					<p dir="ltr" className="font-mono text-xs text-muted">
						{ip}
					</p>
				) : null}
				{place ? (
					<p dir="ltr" className="text-xs text-muted">
						{place}
					</p>
				) : null}
			</div>
		</div>
	);
}
