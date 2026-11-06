import { AppShell, Button, OfflineBanner, ThemeToggle } from "@nyxon/nasim";
import { Outlet, useRouterState } from "@tanstack/react-router";
import { AuthGate, useRole, useSignOut } from "@/features/auth";
import { LogoutIcon } from "@/shared/icons";
import { t } from "@/strings";
import { BottomBar } from "./BottomBar";
import { Footer } from "@/shared/Footer";
import { isCurrent, NAV } from "./nav";

function Brand() {
	return (
		<span className="flex flex-col leading-tight">
			<span className="text-lg font-bold">{t.brand.name}</span>
			<span className="text-xs text-muted">{t.brand.tagline}</span>
		</span>
	);
}

function Shell() {
	const pathname = useRouterState({ select: (state) => state.location.pathname });
	const role = useRole();
	const { signOut, isPending } = useSignOut();
	const items = NAV.filter((item) => !item.ownerOnly || role === "owner");
	return (
		<AppShell
			brand={<Brand />}
			navLabel={t.nav.label}
			nav={items.map((item) => ({
				href: item.to,
				label: item.label,
				icon: <item.icon className="size-5" />,
				isCurrent: isCurrent(item, pathname),
			}))}
			banner={<OfflineBanner />}
			topbar={
				<>
					<ThemeToggle lightLabel={t.theme.light} darkLabel={t.theme.dark} />
					<Button variant="ghost" size="sm" isPending={isPending} onPress={signOut}>
						<LogoutIcon aria-hidden />
						<span className="hidden sm:inline">{t.shell.logout}</span>
					</Button>
				</>
			}
			sidebarFooter={<Footer />}
		>
			<Outlet />
			<div className="mt-10 border-t border-border pt-4 lg:hidden">
				<Footer />
			</div>
			<div aria-hidden className="h-16 lg:hidden" />
			<BottomBar />
		</AppShell>
	);
}

// The pathless layout every signed-in screen lives in: the auth gate, then the app frame.
export function AppLayout() {
	return (
		<AuthGate>
			<Shell />
		</AuthGate>
	);
}
