import { Button, EmptyState, PageHeader } from "@nyxon/nasim";
import { useState } from "react";
import { useRole } from "@/features/auth";
import { AddIcon } from "@/shared/icons";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { AgentGuide } from "./AgentGuide";
import { CreateKeyDialog } from "./CreateKeyDialog";
import { KeysTable } from "./KeysTable";

// Owner only: the master refuses everyone else, so the page does not even ask.
export function ApiKeysPage() {
	useDocumentTitle(t.apiKeys.title);
	const role = useRole();
	const [creating, setCreating] = useState(false);
	if (role !== "owner") {
		return (
			<EmptyState as="h1" title={t.apiKeys.ownerOnlyTitle} description={t.apiKeys.ownerOnly} />
		);
	}
	return (
		<div className="flex flex-col gap-6">
			<PageHeader
				title={t.apiKeys.title}
				description={t.apiKeys.subtitle}
				actions={
					<Button onPress={() => setCreating(true)}>
						<AddIcon aria-hidden />
						{t.apiKeys.create}
					</Button>
				}
			/>
			<AgentGuide />
			<KeysTable />
			<CreateKeyDialog isOpen={creating} onOpenChange={setCreating} />
		</div>
	);
}
