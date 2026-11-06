import { EmptyState } from "@nyxon/nasim";
import { t } from "@/strings";

export function NotFound() {
	return (
		<EmptyState
			as="h1"
			title={t.notFound.title}
			description={t.notFound.message}
			action={{ label: t.notFound.home, href: "/" }}
		/>
	);
}
