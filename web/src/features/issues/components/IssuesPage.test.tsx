import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Issue, IssuesHistory } from "@/api/generated/model";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

const NOW = Math.floor(Date.now() / 1000);

const user = {
	id: 1,
	name: "T",
	username: null,
	role: "owner",
	has_password: false,
	tg_username: null,
};

const issue = (over: Partial<Issue> = {}): Issue => ({
	id: "server:1:disk",
	server_id: 1,
	server_name: "de-1",
	code: "disk",
	severity: "warning",
	title: "دیسک رو به پر شدن است",
	suggestion: "پاک‌سازی",
	evidence: { disk_pct: 91 },
	recent_24h: 10,
	...over,
});

const history = (over: Partial<IssuesHistory> = {}): IssuesHistory => ({
	range: "24h",
	since: NOW - 86_400,
	summary: [
		{
			key: "server:1:disk",
			code: "disk",
			server_id: 1,
			server_name: "de-1",
			title: "دیسک رو به پر شدن است",
			severity: "critical",
			occurrences: 5,
			total_s: 7200,
			last_at: NOW - 300,
			active_now: true,
			flapping: true,
			evidence: {},
		},
		{
			key: "server:2:cpu",
			code: "cpu",
			server_id: 2,
			server_name: "ir-2",
			title: "مصرف CPU بالاست",
			severity: "warning",
			occurrences: 1,
			total_s: 600,
			last_at: NOW - 7200,
			active_now: false,
			flapping: false,
			evidence: {},
		},
	],
	incidents: [
		{
			id: 2,
			key: "server:1:disk",
			code: "disk",
			server_id: 1,
			server_name: "de-1",
			severity: "critical",
			title: "دیسک رو به پر شدن است",
			opened_at: NOW - 600,
			closed_at: null,
			duration_s: 600,
		},
		{
			id: 1,
			key: "server:2:cpu",
			code: "cpu",
			server_id: 2,
			server_name: "ir-2",
			severity: "warning",
			title: "مصرف CPU بالاست",
			opened_at: NOW - 7800,
			closed_at: NOW - 7200,
			duration_s: 600,
		},
	],
	totals: { occurrences: 6, issues: 2, active_now: 1, critical: 1 },
	...over,
});

type Mocks = { history: (range: string) => IssuesHistory };

function open(entry: string, mocks: Mocks = { history: () => history() }) {
	const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
		const url = new URL(String(input), "http://localhost");
		const path = url.pathname.replace(/^.*\/api\/v1/, "");
		const body: unknown =
			path === "/auth/me"
				? user
				: path === "/issues"
					? [issue()]
					: path === "/issues/history"
						? mocks.history(url.searchParams.get("range") ?? "24h")
						: path === "/servers"
							? [{ id: 1, name: "de-1", country: "DE" }]
							: [];
		return new Response(JSON.stringify(body), {
			status: 200,
			headers: { "Content-Type": "application/json" },
		});
	});
	vi.stubGlobal("fetch", fetchMock);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: [entry] }),
	});
	const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
	render(<AppProviders queryClient={queryClient} router={router} />);
	const historyCalls = () =>
		fetchMock.mock.calls
			.map(([input]) => String(input))
			.filter((url) => url.includes("/issues/history"));
	return { router, historyCalls };
}

describe("IssuesPage", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("opens on the current issues and shows how often one came back", async () => {
		const { historyCalls } = open("/issues");
		expect(await screen.findByText("۱۰ بار در ۲۴ ساعت")).toBeTruthy();
		expect(screen.getByRole("tab", { name: "اکنون" }).getAttribute("aria-selected")).toBe("true");
		expect(historyCalls()).toHaveLength(0);
	});

	it("switches to the history tab and keeps it in the address", async () => {
		const { router, historyCalls } = open("/issues");
		await screen.findByText("۱۰ بار در ۲۴ ساعت");
		await userEvent.click(screen.getByRole("tab", { name: "تاریخچه" }));
		expect(await screen.findByRole("region", { name: "جدول رخدادها" })).toBeTruthy();
		expect(historyCalls()[0]).toContain("range=24h");
		expect(router.state.location.search).toMatchObject({ tab: "history" });
	});

	it("shows the totals, the flapping mark, the state and the flag of the server", async () => {
		open("/issues?tab=history");
		const table = await screen.findByRole("grid", { name: "جدول خلاصهٔ مشکل‌ها" });
		expect(within(table).getByText("ناپایدار")).toBeTruthy();
		expect(within(table).getByText("فعال")).toBeTruthy();
		expect(within(table).getByText("برطرف‌شده")).toBeTruthy();
		expect(within(table).getByText("🇩🇪")).toBeTruthy();
		const stats = screen.getByRole("region", { name: "خلاصهٔ بازه" });
		expect(within(stats).getByText("کل رخدادها")).toBeTruthy();
		expect(within(stats).getByText("۶")).toBeTruthy();
		expect(screen.getByRole("region", { name: "جدول رخدادها" })).toBeTruthy();
		expect(screen.getByText("ادامه دارد")).toBeTruthy();
	});

	it("asks for the chosen range and keeps it in the address", async () => {
		const { router, historyCalls } = open("/issues?tab=history&range=7d", {
			history: (range) => history({ range }),
		});
		await screen.findByRole("grid", { name: "جدول خلاصهٔ مشکل‌ها" });
		expect(historyCalls().every((url) => url.includes("range=7d"))).toBe(true);
		await userEvent.click(screen.getByRole("radio", { name: "۳۰ روز" }));
		await waitFor(() => expect(historyCalls().some((url) => url.includes("range=30d"))).toBe(true));
		expect(router.state.location.search).toMatchObject({ tab: "history", range: "30d" });
	});

	it("filters the summary by text", async () => {
		open("/issues?tab=history");
		const table = await screen.findByRole("grid", { name: "جدول خلاصهٔ مشکل‌ها" });
		await userEvent.type(screen.getByRole("searchbox", { name: "جستجوی سرور یا مشکل" }), "ir-2");
		await waitFor(() => expect(within(table).queryByText("ناپایدار")).toBeNull());
		expect(within(table).getByText("برطرف‌شده")).toBeTruthy();
	});

	it("says so when nothing happened in the range", async () => {
		open("/issues?tab=history", {
			history: () =>
				history({
					summary: [],
					incidents: [],
					totals: { occurrences: 0, issues: 0, active_now: 0, critical: 0 },
				}),
		});
		expect(await screen.findByText("در این بازه مشکلی ثبت نشده")).toBeTruthy();
		expect(screen.queryByRole("grid")).toBeNull();
	});
});
