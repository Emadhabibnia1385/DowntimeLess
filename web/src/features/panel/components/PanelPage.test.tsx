import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PanelOut } from "@/api/generated/model";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";
import { panelFixture } from "@/test/checksFixtures";

const me = (role: string) => ({
	id: 1,
	name: "T",
	username: null,
	role,
	has_password: false,
	workspace: { id: 1, name: "فضای کار اصلی", role, is_personal: true },
	tg_username: null,
});

type Call = { method: string; url: string; body: unknown };

function stub(panel: PanelOut | "error", role = "owner") {
	const calls: Call[] = [];
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
			const url = String(input);
			const method = init?.method ?? "GET";
			calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
			const json = (data: unknown, status = 200) =>
				new Response(JSON.stringify(data), {
					status,
					headers: { "Content-Type": "application/json" },
				});
			if (url.endsWith("/auth/me")) return json(me(role));
			if (url.endsWith("/api/v1/panel")) {
				return panel === "error" ? json({ code: "x", message: "خطای آزمایشی" }, 422) : json(panel);
			}
			if (url.includes("/ignores")) return json({ kind: "inbound", name: "wg0", ignored: true });
			return json([]);
		}),
	);
	return calls;
}

function open(path = "/panel") {
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: [path] }),
	});
	const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
	render(<AppProviders queryClient={queryClient} router={router} />);
}

const rowsOf = (name: string) =>
	within(screen.getByRole("grid", { name })).getAllByRole("row").slice(1);

describe("PanelPage", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("shows the nodes, resellers, user counts and group-less inbounds of the real panel shape", async () => {
		stub(panelFixture());
		open();
		expect(await screen.findByRole("heading", { name: "پنل روی panel-1" })).toBeTruthy();
		const nodes = rowsOf("جدول نودهای پنل");
		expect(nodes).toHaveLength(23);
		expect(screen.getByText("۲۲ از ۲۲ نود فعال وصل است (۲۳ نود در پنل)")).toBeTruthy();
		const dropped = nodes.find((row) => within(row).queryByText("node-06")) as HTMLElement;
		expect(within(dropped).getByText("افت مصرف")).toBeTruthy();
		expect(within(nodes[22]).getByText("غیرفعال")).toBeTruthy();
		const resellers = rowsOf("جدول حجم نماینده‌ها");
		expect(resellers).toHaveLength(40);
		// the fullest first, highlighted
		expect(within(resellers[0]).getByText("بحرانی")).toBeTruthy();
		expect(within(resellers[0]).getByText(/۳٫۵ ساعت/)).toBeTruthy();
		expect(screen.getByText("۳ نماینده از ۴۰ نزدیک سقف یا بحرانی")).toBeTruthy();
		const users = screen.getByRole("region", { name: "جدول وضعیت کاربران" });
		expect(within(users).getByText("۸٬۴۱۰")).toBeTruthy();
		expect(within(users).getByText("۱۳٬۵۷۰")).toBeTruthy();
		expect(screen.getByText("wg0")).toBeTruthy();
		expect(screen.queryAllByTestId("data-cards")).toHaveLength(0); // tables, never stacked cards
	});

	it("sorts resellers by name and back", async () => {
		stub(panelFixture());
		open();
		await screen.findByRole("grid", { name: "جدول حجم نماینده‌ها" });
		await userEvent.click(screen.getByRole("button", { name: "مرتب‌سازی بر پایهٔ نماینده" }));
		expect(within(rowsOf("جدول حجم نماینده‌ها")[0]).getByText("reseller00")).toBeTruthy();
		await userEvent.click(screen.getByRole("button", { name: "مرتب‌سازی بر پایهٔ نماینده" }));
		expect(within(rowsOf("جدول حجم نماینده‌ها")[0]).getByText("reseller39")).toBeTruthy();
	});

	it("lets an admin mark an inbound as group-less on purpose; a viewer only reads", async () => {
		const calls = stub(panelFixture());
		open();
		await userEvent.click(
			await screen.findByRole("button", { name: "علامت عمدی برای اینباند wg0" }),
		);
		await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
		const patch = calls.find((c) => c.method === "PATCH") as Call;
		expect(patch.url).toContain("/servers/9/ignores");
		expect(patch.body).toEqual({ kind: "inbound", name: "wg0", ignored: true });
		vi.unstubAllGlobals();
	});

	it("shows no actions to a viewer", async () => {
		stub(panelFixture(), "viewer");
		open();
		await screen.findByRole("grid", { name: "جدول نودهای پنل" });
		expect(screen.queryByRole("button", { name: /بازنشسته کردن نود/ })).toBeNull();
		expect(screen.queryByRole("button", { name: /علامت عمدی/ })).toBeNull();
	});

	it("has an empty state, an error state and a read error notice", async () => {
		stub({ ...panelFixture(), panels: [] });
		open();
		expect(await screen.findByText("هیچ سروری اطلاعات پنل نمی‌فرستد")).toBeTruthy();
	});

	it("shows the error state with a retry", async () => {
		stub("error");
		open();
		expect(await screen.findByText("خطای آزمایشی")).toBeTruthy();
		expect(screen.getByRole("button", { name: "تلاش دوباره" })).toBeTruthy();
	});

	it("names a failed panel read", async () => {
		stub(panelFixture({ available: false, panel_error: "Timeout", nodes: [], resellers: [] }));
		open();
		expect(await screen.findByText(/خواندن پنل ناموفق بود \(Timeout\)/)).toBeTruthy();
	});

	it("puts the page in the navigation only while a server reports a panel", async () => {
		stub(panelFixture());
		open("/ssl");
		expect((await screen.findAllByRole("link", { name: "پنل PasarGuard" })).length).toBeGreaterThan(
			0,
		);
		vi.unstubAllGlobals();
	});

	it("hides it otherwise", async () => {
		stub({ ...panelFixture(), panels: [] });
		open("/ssl");
		await screen.findAllByRole("link", { name: "گواهی‌های SSL" });
		expect(screen.queryByRole("link", { name: "پنل PasarGuard" })).toBeNull();
	});
});
