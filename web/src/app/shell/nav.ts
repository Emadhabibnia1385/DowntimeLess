import type { ComponentType, SVGProps } from "react";
import {
	AccountIcon,
	DashboardIcon,
	IssuesIcon,
	KeyIcon,
	PingIcon,
	ServerIcon,
	SettingsIcon,
} from "@/shared/icons";
import { t } from "@/strings";

type Icon = ComponentType<SVGProps<SVGSVGElement>>;

export type NavItem = {
	to: "/" | "/servers" | "/issues" | "/ping-matrix" | "/api-keys" | "/settings" | "/account";
	label: string;
	icon: Icon;
	/** Shown in the phone's bottom bar too. */
	primary?: boolean;
	ownerOnly?: boolean;
};

export const NAV: readonly NavItem[] = [
	{ to: "/", label: t.nav.dashboard, icon: DashboardIcon, primary: true },
	{ to: "/servers", label: t.nav.servers, icon: ServerIcon, primary: true },
	{ to: "/issues", label: t.nav.issues, icon: IssuesIcon, primary: true },
	{ to: "/ping-matrix", label: t.nav.pingMatrix, icon: PingIcon, primary: true },
	{ to: "/api-keys", label: t.nav.apiKeys, icon: KeyIcon, ownerOnly: true },
	{ to: "/settings", label: t.nav.settings, icon: SettingsIcon },
	{ to: "/account", label: t.nav.account, icon: AccountIcon },
];

/** Whether the current address belongs to a nav item (the dashboard only on its own path). */
export function isCurrent(item: NavItem, pathname: string): boolean {
	return item.to === "/"
		? pathname === "/"
		: pathname === item.to || pathname.startsWith(`${item.to}/`);
}
