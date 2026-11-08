import { Chip } from "@nyxon/nasim";
import type { ServerOut } from "@/api/generated/model";
import { useCategories } from "@/features/categories";
import { roleLabel } from "../lib/status";
import { ServerStatusChip } from "./ServerStatusChip";

// Status in words, then the role and, when it has one, the category of the server.
export function ServerBadges({ server }: { server: ServerOut }) {
	const categories = useCategories();
	const category = categories.data?.find((item) => item.id === server.category_id)?.name;
	return (
		<>
			<ServerStatusChip status={server.status} size="md" />
			<Chip size="md" variant="soft">
				{roleLabel(server.role)}
			</Chip>
			{category ? (
				<Chip size="md" variant="secondary">
					{category}
				</Chip>
			) : null}
		</>
	);
}
