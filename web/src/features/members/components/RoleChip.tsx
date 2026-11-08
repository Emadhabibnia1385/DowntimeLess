import { StatusChip, type StatusTone } from "@nyxon/nasim";
import { asRole, type Role } from "@/features/auth";
import { AccountIcon, DashboardIcon } from "@/shared/icons";
import { t } from "@/strings";

const TONE: Record<Role, StatusTone> = {
	owner: "success",
	admin: "warning",
	operator: "info",
	viewer: "neutral",
};

/** A role in words with a person mark; the colour only repeats what the word says. */
export function RoleChip({ role }: { role: string }) {
	const known = asRole(role);
	return (
		<StatusChip
			tone={TONE[known]}
			size="sm"
			label={t.members.roles[known]}
			icon={<AccountIcon aria-hidden className="size-3.5" />}
		/>
	);
}

/** Marks the workspace a person owns. */
export function PersonalChip() {
	return (
		<StatusChip
			tone="neutral"
			size="sm"
			label={t.workspace.personal}
			icon={<DashboardIcon aria-hidden className="size-3.5" />}
		/>
	);
}
