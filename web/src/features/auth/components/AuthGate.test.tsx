import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

function signedOutRouter(path: string) {
	vi.stubGlobal(
		"fetch",
		vi.fn(
			async () =>
				new Response(JSON.stringify({ code: "auth.required", message: "x" }), {
					status: 401,
					headers: { "Content-Type": "application/json" },
				}),
		),
	);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: [path] }),
	});
	render(
		<AppProviders
			queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
			router={router}
		/>,
	);
	return router;
}

describe("AuthGate", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("sends a signed-out visitor to the login page once, remembering where they were going", async () => {
		const router = signedOutRouter("/servers/3?range=7d");
		await screen.findByRole("button", { name: "ورود با تلگرام" });
		await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
		expect(router.state.location.href).toBe("/login?redirect=%2Fservers%2F3%3Frange%3D7d");
	});
});
