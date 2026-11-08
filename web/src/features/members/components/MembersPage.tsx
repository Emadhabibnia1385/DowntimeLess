import { Button, EmptyState, Notice, PageHeader } from "@nyxon/nasim";
import { useState } from "react";
import { useMe, useRole, useWorkspace } from "@/features/auth";
import { UserPlusIcon } from "@/shared/icons";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { AddMemberDialog } from "./AddMemberDialog";
import { MembersTable } from "./MembersTable";

// Owner only, like the API keys: the master refuses everyone else, so the page does not ask.
export function MembersPage() {
	useDocumentTitle(t.members.title);
	const role = useRole();
	const workspace = useWorkspace();
	// adding people opens the panel to them, so only the panel owner does it
	const canAdd = useMe().data?.is_panel_owner === true;
	const [adding, setAdding] = useState(false);
	if (role !== "owner") {
		return (
			<EmptyState as="h1" title={t.members.ownerOnlyTitle} description={t.members.ownerOnly} />
		);
	}
	return (
		<div className="flex flex-col gap-6">
			<PageHeader
				title={t.members.title}
				description={workspace ? `${t.members.subtitle} · ${workspace.name}` : t.members.subtitle}
				actions={
					canAdd ? (
						<Button onPress={() => setAdding(true)}>
							<UserPlusIcon aria-hidden />
							{t.members.add}
						</Button>
					) : undefined
				}
			/>
			<Notice tone="info">{canAdd ? t.members.intro : t.members.panelOwnerOnly}</Notice>
			<MembersTable />
			<AddMemberDialog isOpen={adding} onOpenChange={setAdding} />
		</div>
	);
}
