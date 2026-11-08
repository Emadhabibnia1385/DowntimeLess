import { Button, ThemeToggle } from "@nyxon/nasim";
import { useMe, useSignOut } from "@/features/auth";
import { LogoutIcon } from "@/shared/icons";
import { t } from "@/strings";
import { InstallButton } from "./InstallButton";

// The bottom of the sidebar and of the phone's menu: install, the signed-in person, theme, logout.
export function SidebarAccount() {
	const me = useMe();
	const { signOut, isPending } = useSignOut();
	const name = me.data?.name ?? t.shell.account;
	const workspace = me.data?.workspace?.name;
	return (
		<div className="flex flex-col gap-4">
			<InstallButton />
			<div className="flex items-center gap-2">
				<ThemeToggle lightLabel={t.theme.light} darkLabel={t.theme.dark} />
				<span className="flex min-w-0 flex-1 flex-col items-center leading-tight">
					<span className="max-w-full truncate text-sm font-medium" title={name}>
						{name}
					</span>
					{workspace ? (
						<span className="max-w-full truncate text-xs text-muted" title={workspace}>
							{workspace}
						</span>
					) : null}
				</span>
				<Button
					isIconOnly
					variant="ghost"
					className="size-11 min-h-11 min-w-11 rounded-full"
					aria-label={t.shell.logout}
					isPending={isPending}
					onPress={signOut}
				>
					<LogoutIcon aria-hidden />
				</Button>
			</div>
		</div>
	);
}
