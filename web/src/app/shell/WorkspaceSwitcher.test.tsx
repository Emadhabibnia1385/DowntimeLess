import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { UserOut, WorkspaceOut } from "@/api/generated/model";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";
import { safePathAfterSwitch } from "./workspacePath";

const MAIN: WorkspaceOut = { id: 1, name: "فضای کار اصلی", role: "owner", is_personal: true };
const OTHER: WorkspaceOut = { id: 2, name: "ناوگان مبین", role: "viewer", is_personal: false };
const me = (workspace: WorkspaceOut): UserOut => ({
	id: 1,
	name: "امید",
	username: null,
	role: workspace.role,
	has_password: false,
	tg_username: null,
	workspace,
});

const json = (body: unknown, status = 200) =>
	new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

type Call = { method: string; url: string; body: unknown };

function boot(path: string) {
	const calls: Call[] = [];
	let active = MAIN;
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
			const url = String(input);
			const method = init?.method ?? "GET";
			calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : null });
			if (url.endsWith("/auth/workspace") && method === "POST") {
				active = OTHER;
				return json(me(OTHER));
			}
			if (url.endsWith("/auth/me")) return json(me(active));
			if (url.endsWith("/auth/workspaces")) return json([MAIN, OTHER]);
			if (url.includes("/servers/5")) return json({ code: "server.not_found", message: "x" }, 404);
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
	return { calls, router };
}

const pill = () => screen.findByRole("button", { name: /فضای کار: فضای کار اصلی/ });

describe("the workspace switcher", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("shows the current workspace and lists mine with my role and the personal one marked", async () => {
		boot("/servers");
		await userEvent.click(await pill());
		const menu = await screen.findByRole("menu");
		const items = within(menu).getAllByRole("menuitemradio");
		expect(items.map((item) => item.textContent)).toEqual([
			expect.stringContaining("فضای کار اصلی"),
			expect.stringContaining("ناوگان مبین"),
		]);
		expect(items[0]?.getAttribute("aria-checked")).toBe("true");
		expect(items[1]?.getAttribute("aria-checked")).toBe("false");
		expect(within(items[0] as HTMLElement).getByText("شخصی")).toBeTruthy();
		expect(within(items[0] as HTMLElement).getByText("مالک")).toBeTruthy();
		expect(within(items[1] as HTMLElement).getByText("بیننده")).toBeTruthy();
	});

	it("switches through the API, then asks for every list again", async () => {
		const { calls } = boot("/servers");
		await userEvent.click(await pill());
		await waitFor(() => expect(calls.some((c) => c.url.endsWith("/api/v1/servers"))).toBe(true));
		const before = calls.filter((c) => c.url.endsWith("/api/v1/servers")).length;
		await userEvent.click(await screen.findByRole("menuitemradio", { name: /ناوگان مبین/ }));
		await waitFor(() =>
			expect(calls.find((c) => c.method === "POST")).toEqual({
				method: "POST",
				url: "/api/v1/auth/workspace",
				body: { workspace_id: 2 },
			}),
		);
		await waitFor(() =>
			expect(calls.filter((c) => c.url.endsWith("/api/v1/servers")).length).toBeGreaterThan(before),
		);
		expect(await screen.findByRole("button", { name: /فضای کار: ناوگان مبین/ })).toBeTruthy();
		expect(await screen.findByText("حالا در «ناوگان مبین» هستید.")).toBeTruthy();
	});

	it("leaves a server of the old workspace for the dashboard", async () => {
		const { router } = boot("/servers/5");
		await userEvent.click(await pill());
		await userEvent.click(await screen.findByRole("menuitemradio", { name: /ناوگان مبین/ }));
		await waitFor(() => expect(router.state.location.pathname).toBe("/"));
	});

	it("keeps every other page", () => {
		expect(safePathAfterSwitch("/servers/12")).toBe("/");
		expect(safePathAfterSwitch("/servers")).toBeNull();
		expect(safePathAfterSwitch("/members")).toBeNull();
		expect(safePathAfterSwitch("/")).toBeNull();
	});
});
