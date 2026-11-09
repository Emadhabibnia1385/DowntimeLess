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
	tg_linked: true,
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

function boot(role = "owner", panelOwner = role === "owner", registrationOpen = true) {
	const calls: Call[] = [];
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
			const url = String(input);
			const method = init?.method ?? "GET";
			calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : null });
			const body = url.endsWith("/auth/me")
				? me(role, panelOwner)
				: url.endsWith("/auth/registration")
					? { open: registrationOpen }
					: url.endsWith("/members/invites") && method === "POST"
						? {
								id: 9,
								tg_username: "new_friend",
								role: "operator",
								name: "",
								created_at: 1,
								expires_at: 2,
							}
						: url.endsWith("/members/invites")
							? []
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

	it("adds by numeric Telegram id, invites by @username and refuses anything else", async () => {
		const calls = boot();
		await userEvent.click(await screen.findByRole("button", { name: "افزودن عضو" }));
		let dialog = await screen.findByRole("dialog");
		const who = within(dialog).getByRole("textbox", { name: /چه کسی/ });
		for (const role of ["بیننده", "اپراتور", "ادمین"]) {
			expect(within(dialog).getByRole("radio", { name: new RegExp(role) })).toBeTruthy();
		}
		expect(within(dialog).queryByRole("radio", { name: /مالک/ })).toBeNull();
		await userEvent.type(who, "@ab");
		await userEvent.click(within(dialog).getByRole("button", { name: "افزودن" }));
		expect(await within(dialog).findByText(/این ورودی شناسهٔ عددی/)).toBeTruthy();
		await userEvent.clear(who);
		await userEvent.type(who, "@new_friend");
		expect(within(dialog).getByText(/دعوت ۱۴ روزه ساخته می‌شود/)).toBeTruthy();
		await userEvent.click(within(dialog).getByRole("button", { name: "افزودن" }));
		expect(await within(dialog).findByText(/فقط برای بیننده یا اپراتور است/)).toBeTruthy();
		expect(calls.some((c) => c.method === "POST")).toBe(false);
		await userEvent.click(within(dialog).getByRole("radio", { name: /اپراتور/ }));
		await userEvent.click(within(dialog).getByRole("button", { name: "افزودن" }));
		await waitFor(() =>
			expect(
				calls.find((c) => c.method === "POST" && c.url.endsWith("/members/invites"))?.body,
			).toEqual({
				tg_username: "new_friend",
				name: null,
				role: "operator",
			}),
		);
		await userEvent.click(await screen.findByRole("button", { name: "افزودن عضو" }));
		dialog = await screen.findByRole("dialog");
		await userEvent.type(within(dialog).getByRole("textbox", { name: /چه کسی/ }), "۵۵۵۶۶۶");
		await userEvent.click(within(dialog).getByRole("radio", { name: /اپراتور/ }));
		await userEvent.click(within(dialog).getByRole("button", { name: "افزودن" }));
		await waitFor(() =>
			expect(calls.find((c) => c.method === "POST" && c.url.endsWith("/members"))?.body).toEqual({
				who: "555666",
				name: null,
				role: "operator",
			}),
		);
	});

	it("is the owner's page only", async () => {
		const calls = boot("admin");
		expect(await screen.findByRole("heading", { level: 1, name: "دسترسی محدود" })).toBeTruthy();
		expect(screen.queryByRole("button", { name: "افزودن عضو" })).toBeNull();
		expect(calls.some((c) => c.url.endsWith("/members"))).toBe(false);
		expect(screen.queryByRole("link", { name: "اعضا" })).toBeNull();
	});

	it("with registration closed another workspace's owner adds existing accounts only", async () => {
		boot("owner", false, false);
		expect(await screen.findByRole("grid", { name: "فهرست اعضا" })).toBeTruthy();
		expect(screen.getByRole("button", { name: "افزودن عضو" })).toBeTruthy();
		expect(await screen.findByText(/افراد تازه را فقط مالک پنل اضافه می‌کند/)).toBeTruthy();
		expect(screen.queryByText("ثبت‌نام در پنل")).toBeNull();
		expect(screen.getByRole("button", { name: "حذف سارا" })).toBeTruthy();
	});

	it("gives the panel owner the registration switch", async () => {
		const calls = boot("owner", true, true);
		const toggle = await screen.findByRole("switch", { name: "ثبت‌نام باز است" });
		await waitFor(() => expect((toggle as HTMLInputElement).checked).toBe(true));
		await userEvent.click(toggle);
		await waitFor(() =>
			expect(
				calls.find((c) => c.method === "PUT" && c.url.endsWith("/auth/registration"))?.body,
			).toEqual({
				open: false,
			}),
		);
	});

	it("puts the members page in the owner's navigation", async () => {
		boot();
		expect((await screen.findAllByRole("link", { name: "اعضا" })).length).toBeGreaterThan(0);
	});
});
