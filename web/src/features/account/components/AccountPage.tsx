import { Button, KeyValueList, PageHeader, SectionCard } from "@nyxon/nasim";
import { Loadable } from "@/shared/Loadable";
import { useMe, useSignOut } from "@/features/auth";
import { LogoutIcon } from "@/shared/icons";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { PasswordForm } from "./PasswordForm";

const ROLES: Record<string, string> = t.account.roles;

export function AccountPage() {
	useDocumentTitle(t.account.title);
	const me = useMe();
	const { signOut, isPending } = useSignOut();
	return (
		<div className="flex flex-col gap-6">
			<PageHeader
				title={t.account.title}
				description={t.account.subtitle}
				actions={
					<Button variant="secondary" isPending={isPending} onPress={signOut}>
						<LogoutIcon aria-hidden />
						{t.account.logout}
					</Button>
				}
			/>
			<Loadable query={me}>
				{(user) => (
					<>
						<SectionCard title={t.account.profile}>
							<KeyValueList
								layout="grid"
								items={[
									{ label: t.account.name, value: user.name },
									{ label: t.account.role, value: ROLES[user.role] ?? user.role },
									user.username
										? { label: t.account.username, value: user.username, ltr: true }
										: null,
									user.tg_username
										? { label: t.account.telegram, value: `@${user.tg_username}`, ltr: true }
										: null,
								]}
							/>
						</SectionCard>
						<SectionCard title={t.account.password}>
							<PasswordForm user={user} />
						</SectionCard>
					</>
				)}
			</Loadable>
		</div>
	);
}
