import { AppShell, OfflineBanner } from "@nyxon/nasim";
import { Outlet, useRouterState } from "@tanstack/react-router";
import { AuthGate, useRole } from "@/features/auth";
import { Footer } from "@/shared/Footer";
import { t } from "@/strings";
import { BottomBar } from "./BottomBar";
import { Brand } from "./Brand";
import { isCurrent, NAV } from "./nav";
import { SidebarAccount } from "./SidebarAccount";
import { TopClock } from "./TopClock";

function Shell() {
	const pathname = useRouterState({ select: (state) => state.location.pathname });
	const role = useRole();
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
			topbar={<TopClock />}
			sidebarFooter={<SidebarAccount />}
		>
			<Outlet />
			<Footer sidebar />
			<div aria-hidden className="h-12" />
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
