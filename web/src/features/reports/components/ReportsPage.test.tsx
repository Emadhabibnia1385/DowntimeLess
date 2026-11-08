import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

const NOW = Math.floor(Date.now() / 1000);
const MD = "# Fleet briefing\n| server | code |\n| de-1 | disk |\n";

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

const playbook = {
	matched: true,
	playbook: {
		code: "offline",
		theme: "host",
		title: "Server stopped reporting",
		summary_fa: "سرور گزارش نمی‌دهد",
		detector: "live",
		causes: ["Provider quota suspension"],
		checks: ["nc -zv -w 5 HOST PORT"],
		fixes: ["Top up the quota"],
		never: ["Never remove a relay on one probe"],
		source: ["incidents.md 68"],
	},
};

function open(entry: string) {
	const writeText = vi.fn(async () => {});
	Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
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
		if (path === "/reports/briefing") {
			return new Response(url.searchParams.get("detail") === "full" ? `${MD}FULL\n` : MD, {
				status: 200,
				headers: { "Content-Type": "text/markdown; charset=utf-8" },
			});
		}
		if (path === "/auth/me") return json(user);
		if (path === "/reports/health") return json(health);
		if (path === "/reports/changes") return json(changes);
		if (path === "/reports/playbooks/offline") return json(playbook);
		if (path === "/reports/playbooks") {
			return json({
				principles: ["p"],
				playbooks: [
					{
						code: "offline",
						theme: "host",
						title: "Server stopped reporting",
						summary_fa: "سرور گزارش نمی‌دهد",
						detector: "live",
					},
					{
						code: "listener_missing",
						theme: "tunnel",
						title: "Expected port is not listening",
						summary_fa: "پورت گوش نمی‌دهد",
						detector: "planned",
					},
				],
			});
		}
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
	return { router, writeText, calls };
}

describe("ReportsPage", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("shows the briefing and copies exactly that text for an assistant", async () => {
		const { writeText } = open("/reports");
		const region = await screen.findByRole("region", { name: "متن خلاصه" });
		expect(region.textContent).toContain("# Fleet briefing");
		await userEvent.click(screen.getByRole("button", { name: "کپی برای هوش مصنوعی" }));
		await waitFor(() => expect(writeText).toHaveBeenCalledWith(MD));
		expect(screen.getByRole("button", { name: "دانلود" })).toBeTruthy();
	});

	it("asks for the full briefing when the detail select says so", async () => {
		const { calls } = open("/reports");
		await screen.findByRole("region", { name: "متن خلاصه" });
		expect(calls.find((c) => c.includes("detail=brief"))).toContain("format=md");
		await userEvent.click(screen.getByRole("button", { name: /میزان جزئیات/ }));
		await userEvent.click(await screen.findByRole("option", { name: "کامل" }));
		await waitFor(() => expect(calls.some((c) => c.includes("detail=full"))).toBe(true));
		expect((await screen.findByRole("region", { name: "متن خلاصه" })).textContent).toContain(
			"FULL",
		);
	});

	it("switches tabs and keeps the tab in the address", async () => {
		const { router } = open("/reports");
		await screen.findByRole("region", { name: "متن خلاصه" });
		await userEvent.click(screen.getByRole("tab", { name: "سلامت" }));
		expect(await screen.findByRole("grid", { name: "جدول امتیاز سلامت" })).toBeTruthy();
		expect(router.state.location.search).toMatchObject({ tab: "health" });
		await userEvent.click(screen.getByRole("tab", { name: "خلاصه برای هوش مصنوعی" }));
		await waitFor(() => expect(router.state.location.search).not.toHaveProperty("tab"));
	});

	it("lists health scores in a table with flags, bands, scores and what cost points", async () => {
		open("/reports?tab=health");
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

	it("shows the change log as a table and filters it by kind", async () => {
		open("/reports?tab=changes");
		const table = await screen.findByRole("grid", { name: "جدول تغییرات" });
		expect(within(table).getByText("نسخهٔ agent از 0.2.7 به 0.2.8")).toBeTruthy();
		expect(within(table).getByText("سرور ریبوت شد")).toBeTruthy();
		await userEvent.click(screen.getByRole("button", { name: /نوع تغییر/ }));
		await userEvent.click(await screen.findByRole("option", { name: "ریبوت" }));
		await waitFor(() =>
			expect(within(table).queryByText("نسخهٔ agent از 0.2.7 به 0.2.8")).toBeNull(),
		);
		expect(within(table).getByText("سرور ریبوت شد")).toBeTruthy();
	});

	it("asks for the chosen period", async () => {
		const { calls } = open("/reports?tab=changes");
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
	});

	it("lists playbooks with the detector state and opens one in a dialog", async () => {
		open("/reports?tab=playbooks");
		const table = await screen.findByRole("grid", { name: "جدول راهنماها" });
		expect(within(table).getByText("فعال")).toBeTruthy();
		expect(within(table).getByText("برنامه‌ریزی‌شده")).toBeTruthy();
		await userEvent.click(within(table).getByRole("button", { name: "مشاهدهٔ راهنمای offline" }));
		const dialog = await screen.findByRole("dialog");
		expect(within(dialog).getByText("Provider quota suspension")).toBeTruthy();
		expect(within(dialog).getByText("nc -zv -w 5 HOST PORT")).toBeTruthy();
		expect(within(dialog).getByText("Never remove a relay on one probe")).toBeTruthy();
		expect(within(dialog).getByText("incidents.md 68")).toBeTruthy();
	});

	it("is in the navigation", async () => {
		open("/reports");
		const nav = (await screen.findAllByRole("link", { name: "گزارش‌ها" }))[0];
		expect(nav?.getAttribute("href")).toBe("/reports");
	});
});
