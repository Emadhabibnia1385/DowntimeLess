import { Link } from "@tanstack/react-router";
import type { ServerOut } from "@/api/generated/model";
import { flagOf, placeLine } from "@/strings";
import { displayName } from "../lib/status";

// The flag, the Persian name (a link to the server) and, under it, country, city and data center.
export function ServerNameCell({ server }: { server: ServerOut }) {
	const place = placeLine(server);
	return (
		<div className="flex items-center gap-2">
			<span aria-hidden className="text-2xl leading-none">
				{flagOf(server.country)}
			</span>
			<div className="min-w-0">
				<Link
					to="/servers/$serverId"
					params={{ serverId: String(server.id) }}
					className="font-semibold text-accent-soft-foreground underline-offset-4 hover:underline"
				>
					{displayName(server)}
				</Link>
				{place ? <p className="text-xs text-muted">{place}</p> : null}
			</div>
		</div>
	);
}
