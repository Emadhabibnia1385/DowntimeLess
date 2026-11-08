import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

const json = (body: unknown) =>
	new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });

function signedInRouter(path: string) {
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL) => {
			const url = String(input);
			if (url.includes("/auth/me"))
				return json({
					id: 1,
					name: "امید",
					role: "owner",
					username: "omid",
					tg_username: null,
					has_password: true,
				});
			return json([]);
		}),
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
}

describe("the signed-in shell", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("puts the signed-in name, theme toggle and logout at the bottom of the sidebar", async () => {
		signedInRouter("/account");
		const sidebar = (await screen.findAllByText("امید"))[0]?.parentElement;
		if (!sidebar) throw new Error("no account row");
		expect(within(sidebar).getByText("امید")).toBeTruthy();
		expect(within(sidebar).getByRole("button", { name: "خروج" })).toBeTruthy();
		expect(within(sidebar).getByRole("button", { name: "روشن" })).toBeTruthy();
	});

	it("shows the official full logo of the dark theme, with the slogan, as the brand", async () => {
		signedInRouter("/account");
		await screen.findAllByText("امید");
		const logos = document.querySelectorAll("img[src='/brand/logo-dark.webp']");
		expect(logos.length).toBeGreaterThan(0);
		expect(screen.getAllByText("قطعی کمتر").length).toBeGreaterThan(0);
	});

	it("has no install button where the browser offers no install", async () => {
		signedInRouter("/account");
		await screen.findAllByText("امید");
		expect(screen.queryByRole("button", { name: "نصب برنامه" })).toBeNull();
	});
});
