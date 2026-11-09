import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { LinkView, UserOut } from "@/api/generated/model";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

const me = (linked: boolean): UserOut => ({
	id: 4,
	name: "",
	username: "sara",
	role: "owner",
	has_password: true,
	tg_username: linked ? "sara_tg" : null,
	tg_linked: linked,
	is_panel_owner: false,
	workspace: { id: 7, name: "sara", role: "owner", is_personal: true },
});

const merging: LinkView = {
	link_id: 5,
	status: "confirmed",
	expires_at: 1_790_000_600,
	telegram: { id: 7300, username: "sara_tg", name: "Sara" },
	merge: {
		survivor: "this",
		other: { username: null, name: "Sara T", has_password: false, tg_username: "sara_tg" },
		workspaces: [
			{
				workspace_id: 1,
				name: "اصلی",
				role: "viewer",
				survivor_role: null,
				result_role: "viewer",
				owned: false,
			},
			{
				workspace_id: 9,
				name: "Sara T",
				role: "owner",
				survivor_role: null,
				result_role: "owner",
				owned: true,
			},
		],
		api_keys: 2,
		moves_password: false,
		keeps_panel_owner: false,
		fingerprint: "f".repeat(32),
	},
};

type Call = { method: string; url: string; body: unknown };

function boot(view: LinkView) {
	const calls: Call[] = [];
	let linked = false;
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
			const url = String(input);
			const method = init?.method ?? "GET";
			calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : null });
			if (url.endsWith("/auth/me")) return Response.json(me(linked));
			if (url.endsWith("/auth/link/start"))
				return Response.json({
					link_id: 5,
					deep_link: "https://t.me/testbot?start=ln_abc",
					expires_in: 600,
				});
			if (url.endsWith("/auth/link/5/confirm")) {
				linked = true;
				return Response.json({
					merged: Boolean(view.merge),
					claimed_workspaces: 0,
					user: me(true),
				});
			}
			if (url.endsWith("/auth/link/5")) return Response.json(view);
			return Response.json([]);
		}),
	);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: ["/account"] }),
	});
	render(
		<AppProviders
			queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
			router={router}
		/>,
	);
	return calls;
}

describe("linking Telegram from the account page", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("shows the full merge plan and merges only after the explicit acknowledgement", async () => {
		const calls = boot(merging);
		await userEvent.click(await screen.findByRole("button", { name: "اتصال حساب تلگرام" }));
		expect(await screen.findByText("این حساب تلگرام به حساب دیگری تعلق دارد")).toBeTruthy();
		const table = screen.getByRole("list", { name: "عضویت‌هایی که منتقل می‌شوند" });
		expect(within(table).getByText("مالکیت منتقل می‌شود")).toBeTruthy();
		expect(screen.getByText(/۲ کلید API/)).toBeTruthy();
		const merge = screen.getByRole("button", { name: "ادغام و اتصال" });
		expect(merge.hasAttribute("disabled") || merge.getAttribute("aria-disabled") === "true").toBe(
			true,
		);
		await userEvent.click(screen.getByRole("checkbox", { name: /یک‌طرفه است/ }));
		expect(merge.hasAttribute("disabled") || merge.getAttribute("aria-disabled") === "true").toBe(
			true,
		); // the bot's code is still missing
		await userEvent.type(screen.getByLabelText("کد تأیید ربات"), "424242");
		await userEvent.click(screen.getByRole("button", { name: "ادغام و اتصال" }));
		await waitFor(() =>
			expect(calls.find((c) => c.url.endsWith("/auth/link/5/confirm"))?.body).toEqual({
				code: "424242",
				merge: true,
				fingerprint: "f".repeat(32),
			}),
		);
		expect(await screen.findByText("وصل است")).toBeTruthy();
	});

	it("links without a merge after one confirmation", async () => {
		const calls = boot({ ...merging, merge: null });
		await userEvent.click(await screen.findByRole("button", { name: "اتصال حساب تلگرام" }));
		await userEvent.type(await screen.findByLabelText("کد تأیید ربات"), "123456");
		await userEvent.click(await screen.findByRole("button", { name: "تأیید اتصال" }));
		await waitFor(() =>
			expect(calls.find((c) => c.url.endsWith("/auth/link/5/confirm"))?.body).toEqual({
				code: "123456",
			}),
		);
	});
});
