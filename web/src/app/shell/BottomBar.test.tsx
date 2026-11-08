import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

const json = (body: unknown) =>
	new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });

function signedIn(path: string) {
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL) => {
			if (String(input).includes("/auth/me"))
				return json({
					id: 1,
					name: "امید",
					role: "owner",
					username: "omid",
					tg_username: null,
					has_password: true,
					workspace: { id: 1, name: "فضای کار اصلی", role: "owner", is_personal: true },
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

const bar = () => screen.findByRole("navigation", { name: "دسترسی سریع" });

describe("the phone bottom bar", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("puts the dashboard in the middle with two screens on each side", async () => {
		signedIn("/servers");
		const items = within(await bar()).getAllByRole("listitem");
		expect(items.map((item) => within(item).getByRole("link").textContent)).toEqual([
			"سرورها",
			"گزارشات",
			"داشبورد",
			"ماتریس پینگ",
			"ترافیک",
		]);
		expect(items[2]?.hasAttribute("data-center")).toBe(true);
		expect(items.filter((item) => item.hasAttribute("data-center"))).toHaveLength(1);
	});

	it("draws the dashboard as a raised accent circle cut out of the bar", async () => {
		signedIn("/servers");
		const link = within(await bar()).getByRole("link", { name: "داشبورد" });
		const orb = link.firstElementChild;
		expect(orb?.className).toContain("size-14");
		expect(orb?.className).toContain("rounded-full");
		expect(orb?.className).toContain("bg-accent");
		expect(orb?.className).toContain("ring-surface");
		expect(link.className).toContain("-mt-7");
		expect(link.getAttribute("aria-current")).toBeNull();
	});

	it("marks the dashboard as the current page on the dashboard only", async () => {
		signedIn("/");
		const nav = await bar();
		const link = within(nav).getByRole("link", { name: "داشبورد" });
		expect(link.getAttribute("aria-current")).toBe("page");
		expect(link.getAttribute("data-status")).toBe("active");
		expect(
			within(nav).getByRole("link", { name: "سرورها" }).getAttribute("aria-current"),
		).toBeNull();
	});
});
