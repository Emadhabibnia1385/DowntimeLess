import { Button, KeyValueList, PageHeader, SectionCard, StatusChip, Tabs } from "@nyxon/nasim";
import type { UserOut } from "@/api/generated/model";
import { asRole, useMe, useSignOut } from "@/features/auth";
import { NotificationsTab } from "@/features/settings";
import { Loadable } from "@/shared/Loadable";
import { LogoutIcon } from "@/shared/icons";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { type AccountTab, isAccountTab } from "../tabs";
import { PasswordForm } from "./PasswordForm";
import { TelegramLink } from "./TelegramLink";

function Profile({ user }: { user: UserOut }) {
	const space = user.workspace;
	return (
		<SectionCard title={t.account.profile}>
			<KeyValueList
				layout="grid"
				items={[
					{ label: t.account.name, value: user.name },
					space
						? {
								label: t.account.workspace,
								value: space.is_personal ? t.account.workspacePersonal(space.name) : space.name,
							}
						: null,
					{ label: t.account.role, value: t.members.roles[asRole(user.role)] },
					user.username ? { label: t.account.username, value: user.username, ltr: true } : null,
				]}
			/>
		</SectionCard>
	);
}

function Messengers({ user }: { user: UserOut }) {
	return (
		<SectionCard title={t.account.messengers}>
			<div className="flex flex-col gap-3">
				<p className="text-sm leading-7 text-muted">{t.account.messengersHint}</p>
				<div className="flex items-center justify-between gap-3 rounded-2xl border border-border p-3">
					<div className="flex flex-col">
						<span className="font-semibold">{t.account.telegram}</span>
						{user.tg_username ? (
							<span dir="ltr" className="text-start text-sm text-muted">
								@{user.tg_username}
							</span>
						) : null}
					</div>
					<StatusChip
						tone={user.tg_linked ? "success" : "neutral"}
						label={user.tg_linked ? t.account.connected : t.account.notConnected}
						size="sm"
					/>
				</div>
				<TelegramLink user={user} />
			</div>
		</SectionCard>
	);
}

function Session() {
	const { signOut, isPending } = useSignOut();
	return (
		<SectionCard title={t.account.session}>
			<div className="flex flex-col items-start gap-3">
				<p className="text-sm leading-7 text-muted">{t.account.sessionHint}</p>
				<Button variant="secondary" isPending={isPending} onPress={signOut}>
					<LogoutIcon aria-hidden />
					{t.account.logout}
				</Button>
			</div>
		</SectionCard>
	);
}

// Two tabs: the person (cards side by side) and every alert as a table.
export function AccountPage({
	tab,
	onTabChange,
}: {
	tab: AccountTab;
	onTabChange: (tab: AccountTab) => void;
}) {
	useDocumentTitle(t.account.title);
	const me = useMe();
	return (
		<div className="flex flex-col gap-6">
			<PageHeader title={t.account.title} description={t.account.subtitle} />
			<Tabs
				label={t.account.tabsLabel}
				selectedKey={tab}
				onSelectionChange={(id) => isAccountTab(id) && onTabChange(id)}
				items={[
					{
						id: "account",
						label: t.account.tabAccount,
						content: (
							<Loadable query={me}>
								{(user) => (
									<div className="grid items-start gap-4 lg:grid-cols-2">
										<div className="flex flex-col gap-4">
											<Profile user={user} />
											<Messengers user={user} />
											<Session />
										</div>
										<SectionCard title={t.account.password}>
											<PasswordForm user={user} />
										</SectionCard>
									</div>
								)}
							</Loadable>
						),
					},
					{ id: "notifications", label: t.account.tabNotifications, content: <NotificationsTab /> },
				]}
			/>
		</div>
	);
}
