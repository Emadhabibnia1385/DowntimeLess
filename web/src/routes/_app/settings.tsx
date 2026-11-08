import { createFileRoute, redirect } from "@tanstack/react-router";

// The alert settings moved into the account page; an old bookmark lands on its tab.
export const Route = createFileRoute("/_app/settings")({
	beforeLoad: () => {
		throw redirect({ to: "/account", search: { tab: "notifications" }, replace: true });
	},
});
