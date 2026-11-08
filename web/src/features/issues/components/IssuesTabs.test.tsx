import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

const NOW = Math.floor(Date.now() / 1000);

const user = {
	id: 1,
	name: "T",
	username: null,
	role: "owner",
	has_password: false,
	workspace: { id: 1, name: "فضای کار اصلی", role: "owner", is_personal: true },
	tg_username: null,
};

const health = {
	generated_at: NOW,
	counts: { healthy: 1, degraded: 0, failing: 1, unknown: 0 },
	description: "d",
	weights: {},
	not_measured: {},
	quota_measured: false,
	servers: [
		{
			server_id: 2,
			name: "ir-2",
			role: "relay",
			country: "IR",
			category_id: null,
			status: "online",
			variant: "relay",
			score: 40,
			band: "failing",
			gates: [{ key: "conntrack_full", detail: "x" }],
			penalties: [{ key: "retrans", points: 15, max: 15, detail: "x" }],
			open_issues: 2,
			not_measured: [],
		},
		{
			server_id: 1,
			name: "de-1",
			role: "exit",
			country: "DE",
			category_id: null,
			status: "online",
			variant: "exit",
			score: 100,
			band: "healthy",
			gates: [],
			penalties: [],
			open_issues: 0,
			not_measured: [],
		},
	],
};

const changes = {
	since: NOW - 86_400,
	until: NOW,
	truncated: false,
	events: [
		{
			id: 2,
			ts: NOW - 60,
			server_id: 1,
			server: "de-1",
			kind: "agent_updated",
			title: "x",
			detail: { old: "0.2.7", new: "0.2.8" },
		},
		{
			id: 1,
			ts: NOW - 600,
			server_id: 2,
			server: "ir-2",
			kind: "rebooted",
			title: "x",
			detail: {},
		},
	],
};

function open(entry: string) {
	const calls: string[] = [];
	const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
		const url = new URL(String(input), "http://localhost");
		const path = url.pathname.replace(/^.*\/api\/v1/, "");
		calls.push(path + url.search);
		const json = (body: unknown) =>
			new Response(JSON.stringify(body), {
				status: 200,
				headers: { "Content-Type": "application/json" },
			});
		if (path === "/auth/me") return json(user);
		if (path === "/reports/health") return json(health);
		if (path === "/reports/changes") return json(changes);
		if (path === "/servers") return json([{ id: 1, name: "de-1", country: "DE" }]);
		return json([]);
	});
	vi.stubGlobal("fetch", fetchMock);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: [entry] }),
	});
	const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
	render(<AppProviders queryClient={queryClient} router={router} />);
	return { router, calls };
}

describe("Issues page: health and changes tabs", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("has the tabs in order: now, history, health, changes", async () => {
		open("/issues");
		await screen.findAllByRole("tab");
		expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
			"اکنون",
			"تاریخچه",
			"سلامت",
			"تغییرات",
		]);
	});

	it("switches to health and changes and keeps the tab in the address", async () => {
		const { router } = open("/issues");
		await userEvent.click(await screen.findByRole("tab", { name: "سلامت" }));
		expect(await screen.findByRole("grid", { name: "جدول امتیاز سلامت" })).toBeTruthy();
		expect(router.state.location.search).toMatchObject({ tab: "health" });
		await userEvent.click(screen.getByRole("tab", { name: "تغییرات" }));
		expect(await screen.findByRole("grid", { name: "جدول تغییرات" })).toBeTruthy();
		expect(router.state.location.search).toMatchObject({ tab: "changes" });
		await userEvent.click(screen.getByRole("tab", { name: "اکنون" }));
		await waitFor(() => expect(router.state.location.search).not.toHaveProperty("tab"));
	});

	it("lists health scores in a table with flags, bands, scores and what cost points", async () => {
		open("/issues?tab=health");
		const table = await screen.findByRole("grid", { name: "جدول امتیاز سلامت" });
		expect(within(table).getByText("ir-2")).toBeTruthy();
		expect(within(table).getByText("ناسالم")).toBeTruthy();
		expect(within(table).getByText("سالم")).toBeTruthy();
		expect(within(table).getByText("۴۰")).toBeTruthy();
		expect(within(table).getByText("conntrack پر شده")).toBeTruthy();
		expect(within(table).getByText("ارسال مجدد TCP")).toBeTruthy();
		expect(within(table).getByText("🇩🇪")).toBeTruthy();
		await userEvent.type(screen.getByRole("searchbox", { name: "جستجوی سرور" }), "de-");
		await waitFor(() => expect(within(table).queryByText("ir-2")).toBeNull());
		expect(within(table).getByText("de-1")).toBeTruthy();
	});

	it("keeps the health band filter in the address", async () => {
		const { router } = open("/issues?tab=health&band=failing");
		const table = await screen.findByRole("grid", { name: "جدول امتیاز سلامت" });
		expect(within(table).getByText("ir-2")).toBeTruthy();
		expect(within(table).queryByText("de-1")).toBeNull();
		await userEvent.click(screen.getByRole("button", { name: /ناسالم/ }));
		await userEvent.click(await screen.findByRole("option", { name: "همهٔ وضعیت‌ها" }));
		await waitFor(() => expect(router.state.location.search).not.toHaveProperty("band"));
		expect(await within(table).findByText("de-1")).toBeTruthy();
	});

	it("shows the change log as a table and filters it by kind in the address", async () => {
		const { router } = open("/issues?tab=changes");
		const table = await screen.findByRole("grid", { name: "جدول تغییرات" });
		expect(within(table).getByText("نسخهٔ agent از 0.2.7 به 0.2.8")).toBeTruthy();
		expect(within(table).getByText("سرور ریبوت شد")).toBeTruthy();
		await userEvent.click(screen.getByRole("button", { name: /نوع تغییر/ }));
		await userEvent.click(await screen.findByRole("option", { name: "ریبوت" }));
		await waitFor(() =>
			expect(within(table).queryByText("نسخهٔ agent از 0.2.7 به 0.2.8")).toBeNull(),
		);
		expect(within(table).getByText("سرور ریبوت شد")).toBeTruthy();
		expect(router.state.location.search).toMatchObject({ tab: "changes", kind: "rebooted" });
	});

	it("asks for the chosen period and keeps it in the address", async () => {
		const { calls, router } = open("/issues?tab=changes");
		await screen.findByRole("grid", { name: "جدول تغییرات" });
		const first = calls.find((c) => c.startsWith("/reports/changes")) ?? "";
		const since = Number(new URL(first, "http://x").searchParams.get("since"));
		expect(NOW - since).toBeGreaterThan(86_000);
		expect(NOW - since).toBeLessThan(87_000);
		await userEvent.click(screen.getByRole("button", { name: /بازه/ }));
		await userEvent.click(await screen.findByRole("option", { name: "۷ روز" }));
		await waitFor(() => {
			const last = calls.filter((c) => c.startsWith("/reports/changes")).at(-1) ?? "";
			expect(NOW - Number(new URL(last, "http://x").searchParams.get("since"))).toBeGreaterThan(
				600_000,
			);
		});
		expect(router.state.location.search).toMatchObject({ tab: "changes", period: "7d" });
	});

	it("opens the right tab from the address and ignores unknown filter values", async () => {
		open("/issues?tab=changes&period=1y&kind=nope");
		expect(await screen.findByRole("grid", { name: "جدول تغییرات" })).toBeTruthy();
		expect(screen.getByRole("tab", { name: "تغییرات" }).getAttribute("aria-selected")).toBe("true");
	});

	it("sends an old /reports bookmark to the health tab", async () => {
		const { router } = open("/reports");
		expect(await screen.findByRole("grid", { name: "جدول امتیاز سلامت" })).toBeTruthy();
		expect(router.state.location.pathname).toBe("/issues");
		expect(router.state.location.search).toMatchObject({ tab: "health" });
	});

	it("sends /reports?tab=changes to the changes tab and other old tabs to health", async () => {
		const { router } = open("/reports?tab=changes");
		expect(await screen.findByRole("grid", { name: "جدول تغییرات" })).toBeTruthy();
		expect(router.state.location.pathname).toBe("/issues");
		expect(router.state.location.search).toMatchObject({ tab: "changes" });
		await router.navigate({ to: "/reports", search: {} });
		expect(router.state.location.pathname).toBe("/issues");
		await router.navigate({ href: "/reports?tab=playbooks" });
		await waitFor(() => expect(router.state.location.search).toMatchObject({ tab: "health" }));
	});

	it("has no reports item in the navigation", async () => {
		open("/issues");
		expect((await screen.findAllByRole("link", { name: "مشکلات" })).length).toBeGreaterThan(0);
		expect(screen.queryByRole("link", { name: "گزارش‌ها" })).toBeNull();
		expect(document.querySelector('a[href="/reports"]')).toBeNull();
	});
});
