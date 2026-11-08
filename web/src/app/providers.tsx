import { NasimProvider } from "@nyxon/nasim";
import { type QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type AnyRouter, RouterProvider } from "@tanstack/react-router";
import { routerLinks } from "./routerLinks";
import { palette } from "./theme/palette";
import { ErrorBoundary } from "./shell/ErrorBoundary";

export function AppProviders({
	queryClient,
	router,
}: {
	queryClient: QueryClient;
	router: AnyRouter;
}) {
	return (
		<QueryClientProvider client={queryClient}>
			<NasimProvider {...routerLinks(router)} palette={palette} defaultMode="dark">
				<ErrorBoundary>
					<RouterProvider router={router} />
				</ErrorBoundary>
			</NasimProvider>
		</QueryClientProvider>
	);
}
