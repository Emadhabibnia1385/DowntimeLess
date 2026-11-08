import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { AccountPage, type AccountTab, isAccountTab } from "@/features/account";

export const Route = createFileRoute("/_app/account")({
	// The open tab lives in the address so a reload or a shared link keeps it.
	validateSearch: (search: Record<string, unknown>): { tab?: AccountTab } => ({
		tab: isAccountTab(search.tab) ? search.tab : undefined,
	}),
	component: AccountRoute,
});

function AccountRoute() {
	const { tab } = Route.useSearch();
	const navigate = useNavigate({ from: Route.fullPath });
	return (
		<AccountPage
			tab={tab ?? "account"}
			onTabChange={(next) => void navigate({ search: { tab: next }, replace: true })}
		/>
	);
}
