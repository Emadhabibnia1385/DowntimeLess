import { Button, EmptyState, Notice, PageHeader } from "@nyxon/nasim";
import { useState } from "react";
import { useAuthRegistration } from "@/api/generated/auth/auth";
import { useMe, useRole, useWorkspace } from "@/features/auth";
import { UserPlusIcon } from "@/shared/icons";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { AddMemberDialog } from "./AddMemberDialog";
import { InvitesCard } from "./InvitesCard";
import { MembersTable } from "./MembersTable";
import { RegistrationCard } from "./RegistrationCard";

// Owner only, like the API keys: the master refuses everyone else, so the page does not ask.
export function MembersPage() {
	useDocumentTitle(t.members.title);
	const role = useRole();
	const workspace = useWorkspace();
	const panelOwner = useMe().data?.is_panel_owner === true;
	// with registration closed only the panel owner brings new people; anyone may add existing accounts
	const open = useAuthRegistration().data?.open ?? true;
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
					<Button onPress={() => setAdding(true)}>
						<UserPlusIcon aria-hidden />
						{t.members.add}
					</Button>
				}
			/>
			<Notice tone="info">
				{open || panelOwner ? t.members.intro : t.members.newPeopleClosed}
			</Notice>
			{panelOwner ? <RegistrationCard /> : null}
			<MembersTable />
			<InvitesCard />
			<AddMemberDialog isOpen={adding} onOpenChange={setAdding} />
		</div>
	);
}
