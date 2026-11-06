import { createFileRoute } from "@tanstack/react-router";
import { LoginPage } from "@/features/auth";

export const Route = createFileRoute("/login")({
	// Where to return after signing in; the page only ever follows a path on this site.
	validateSearch: (search: Record<string, unknown>) => ({
		redirect: typeof search.redirect === "string" ? search.redirect : undefined,
	}),
	component: LoginRoute,
});

function LoginRoute() {
	const { redirect } = Route.useSearch();
	return <LoginPage redirect={redirect} />;
}
