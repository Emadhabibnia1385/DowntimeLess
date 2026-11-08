import { KeyValueList, SectionCard } from "@nyxon/nasim";
import type { ServerOut } from "@/api/generated/model";
import { useCategories } from "@/features/categories";
import { t } from "@/strings";
import { infoItems } from "./infoItems";

// The record of one server in two columns: place, system, agent and last report.
export function ServerInfo({ server }: { server: ServerOut }) {
	const categories = useCategories();
	const category = categories.data?.find((item) => item.id === server.category_id)?.name;
	return (
		<SectionCard title={t.server.details}>
			<KeyValueList layout="grid" items={infoItems(server, category)} />
		</SectionCard>
	);
}
