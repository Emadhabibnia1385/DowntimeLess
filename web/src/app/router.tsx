import { createRouter } from "@tanstack/react-router";
import { routeTree } from "@/routeTree.gen";
import { RouteError } from "./shell/ErrorBoundary";
import { NotFound } from "./shell/NotFound";
import { PageSkeleton } from "./shell/PageSkeleton";

export const router = createRouter({
	routeTree,
	defaultPreload: "intent",
	scrollRestoration: true,
	defaultNotFoundComponent: NotFound,
	defaultErrorComponent: RouteError,
	// A slow route chunk shows a skeleton after a beat instead of a blank area.
	defaultPendingComponent: PageSkeleton,
	defaultPendingMs: 200,
});

declare module "@tanstack/react-router" {
	interface Register {
		router: typeof router;
	}
}
