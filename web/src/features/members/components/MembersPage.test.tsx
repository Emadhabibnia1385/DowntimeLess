import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MemberOut, UserOut } from "@/api/generated/model";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

const me = (role: string, panelOwner = role === "owner"): UserOut => ({
	is_panel_owner: panelOwner,
	id: 1,
	name: "امید",
	username: null,
	role,
	has_password: false,
	tg_username: null,
	workspace: { id: 1, name: "فضای کار اصلی", role, is_personal: role === "owner" },
});

const member = (over: Partial<MemberOut>): MemberOut => ({
	user_id: 2,
	name: "سارا",
	tg_id: 123456789,
	tg_username: null,
	role: "operator",
	last_login: null,
	added_at: 1,
	is_me: false,
	...over,
});

const MEMBERS = [
	member({
		user_id: 1,
		name: "امید",
		tg_id: 111,
		role: "owner",
		is_me: true,
		last_login: 1_790_000_000,
	}),
	member({}),
];

type Call = { method: string; url: string; body: unknown };

function boot(role = "owner", panelOwner = role === "owner") {
	const calls: Call[] = [];
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
			const url = String(input);
			const method = init?.method ?? "GET";
			calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : null });
			const body = url.endsWith("/auth/me")
				? me(role, panelOwner)
				: url.endsWith("/members") && method === "POST"
					? member({ user_id: 3, name: "رضا", tg_id: 555666 })
					: url.endsWith("/members")
						? MEMBERS
						: url.includes("/members/")
							? member({ role: "admin" })
							: [];
			return new Response(method === "DELETE" ? null : JSON.stringify(body), {
				status: method === "DELETE" ? 204 : 200,
				headers: { "Content-Type": "application/json" },
			});
		}),
	);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: ["/members"] }),
	});
	render(
		<AppProviders
			queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
			router={router}
		/>,
	);
	return calls;
}

describe("members and access", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("lists the members in a table with the Telegram id, role and last sign-in", async () => {
		boot();
		expect(await screen.findByRole("heading", { level: 1, name: "اعضا و دسترسی‌ها" })).toBeTruthy();
		const table = await screen.findByRole("grid", { name: "فهرست اعضا" });
		const rows = within(table).getAllByRole("row");
		expect(rows).toHaveLength(3);
		expect(within(rows[1] as HTMLElement).getByText("مالک")).toBeTruthy();
		expect(within(rows[1] as HTMLElement).getByText("شما")).toBeTruthy();
		expect(within(rows[1] as HTMLElement).queryByRole("button", { name: /حذف/ })).toBeNull();
		expect(within(rows[2] as HTMLElement).getByText("123456789")).toBeTruthy();
		expect(within(rows[2] as HTMLElement).getByText("هنوز وارد نشده")).toBeTruthy();
		expect(
			within(rows[2] as HTMLElement).getByRole("button", { name: "کپی شناسهٔ تلگرام سارا" }),
		).toBeTruthy();
		expect(within(rows[2] as HTMLElement).getByRole("button", { name: /نقش سارا/ })).toBeTruthy();
	});

	it("removes a member only after a confirmation", async () => {
		const calls = boot();
		await userEvent.click(await screen.findByRole("button", { name: "حذف سارا" }));
		const dialog = await screen.findByRole("alertdialog");
		expect(within(dialog).getByText(/سارا دیگر این فضای کار را نمی‌بیند/)).toBeTruthy();
		expect(calls.some((c) => c.method === "DELETE")).toBe(false);
		await userEvent.click(within(dialog).getByRole("button", { name: "حذف" }));
		await waitFor(() =>
			expect(calls.some((c) => c.method === "DELETE" && c.url.endsWith("/api/v1/members/2"))).toBe(
				true,
			),
		);
	});

	it("adds an admin by numeric Telegram id and refuses anything else", async () => {
		const calls = boot();
		await userEvent.click(await screen.findByRole("button", { name: "افزودن ادمین" }));
		const dialog = await screen.findByRole("dialog");
		const id = within(dialog).getByRole("textbox", { name: /شناسهٔ عددی تلگرام/ });
		for (const role of ["بیننده", "اپراتور", "ادمین"]) {
			expect(within(dialog).getByRole("radio", { name: new RegExp(role) })).toBeTruthy();
		}
		expect(within(dialog).getByText("همه کارها به‌جز اعضا و کلید API")).toBeTruthy();
		expect(within(dialog).queryByRole("radio", { name: /مالک/ })).toBeNull();
		await userEvent.type(id, "abc12");
		await userEvent.click(within(dialog).getByRole("button", { name: "افزودن" }));
		expect(await within(dialog).findByText(/شناسه فقط رقم است/)).toBeTruthy();
		expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/members"))).toBe(false);
		await userEvent.clear(id);
		await userEvent.type(id, "۵۵۵۶۶۶");
		await userEvent.click(within(dialog).getByRole("radio", { name: /اپراتور/ }));
		await userEvent.click(within(dialog).getByRole("button", { name: "افزودن" }));
		await waitFor(() =>
			expect(calls.find((c) => c.method === "POST" && c.url.endsWith("/members"))?.body).toEqual({
				tg_id: 555666,
				name: null,
				role: "operator",
			}),
		);
	});

	it("is the owner's page only", async () => {
		const calls = boot("admin");
		expect(await screen.findByRole("heading", { level: 1, name: "دسترسی محدود" })).toBeTruthy();
		expect(screen.queryByRole("button", { name: "افزودن ادمین" })).toBeNull();
		expect(calls.some((c) => c.url.endsWith("/members"))).toBe(false);
		expect(screen.queryByRole("link", { name: "اعضا" })).toBeNull();
	});

	it("lets only the panel owner add people; another workspace's owner manages roles", async () => {
		boot("owner", false);
		expect(await screen.findByRole("grid", { name: "فهرست اعضا" })).toBeTruthy();
		expect(screen.queryByRole("button", { name: "افزودن ادمین" })).toBeNull();
		expect(screen.getByText(/فقط مالک پنل افراد تازه را اضافه می‌کند/)).toBeTruthy();
		expect(screen.getByRole("button", { name: "حذف سارا" })).toBeTruthy();
	});

	it("puts the members page in the owner's navigation", async () => {
		boot();
		expect((await screen.findAllByRole("link", { name: "اعضا" })).length).toBeGreaterThan(0);
	});
});
