import { Link } from "@tanstack/react-router";

// The server's flag and name; a link to its page when it has one.
export function ServerLabel({
	serverId,
	name,
	flag,
}: {
	serverId: number | null;
	name: string | null;
	flag: string;
}) {
	if (!name) return null;
	return (
		<span className="inline-flex items-center gap-1.5 whitespace-nowrap">
			{flag ? <span aria-hidden>{flag}</span> : null}
			{serverId === null ? (
				<span className="font-medium">{name}</span>
			) : (
				<Link
					to="/servers/$serverId"
					params={{ serverId: String(serverId) }}
					className="font-medium text-accent-soft-foreground underline-offset-4 hover:underline"
				>
					{name}
				</Link>
			)}
		</span>
	);
}
