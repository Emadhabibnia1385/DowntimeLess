import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ServerTraffic, TrafficSeries, TrafficSummary, Volume } from "@/api/generated/model";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";
import { t } from "@/strings";

const GB = 1024 ** 3;
const NOW = Math.floor(Date.now() / 1000);

const user = {
	id: 1,
	name: "T",
	username: null,
	role: "owner",
	has_password: false,
	tg_username: null,
};

const vol = (rx: number, tx: number): Volume => ({ rx, tx, total: rx + tx });

const server = (
	id: number,
	name: string,
	role: string,
	country: string,
	share: number,
	scale: number,
): ServerTraffic => ({
	server_id: id,
	name,
	alias: null,
	role,
	country,
	category_id: null,
	today: vol(scale * 8 * GB, scale * 2 * GB),
	yesterday: vol(scale * 16 * GB, scale * 4 * GB),
	period: vol(scale * 400 * GB, scale * 100 * GB),
	avg_per_day: vol(scale * 20 * GB, scale * 5 * GB),
	active_days: 25,
	peak_day: { date: "2026-10-12", ...vol(scale * 40 * GB, scale * 10 * GB) },
	share_pct: share,
});

const summary = (servers: ServerTraffic[]): TrafficSummary => ({
	generated_at: NOW,
	tz_offset_min: 210,
	since: NOW - 30 * 86_400,
	until: NOW,
	fleet: {
		today: vol(10 * GB, 0),
		yesterday: vol(1.2 * 1024 * GB, 0),
		period: vol(900 * GB, 100 * GB),
		avg_per_day: vol(36 * GB, 4 * GB),
		active_days: 25,
		peak_day: { date: "2026-10-12", ...vol(80 * GB, 20 * GB) },
	},
	servers,
});

const hours = Array.from({ length: 24 }, (_, hour) => ({
	hour,
	rx: hour === 21 ? 5 * GB : GB,
	tx: GB / 2,
}));

const series = (over: Partial<TrafficSeries> = {}): TrafficSeries => ({
	since: NOW - 30 * 86_400,
	until: NOW,
	server_id: null,
	tz_offset_min: 210,
	bucket_s: 86_400,
	points: Array.from({ length: 5 }, (_, index) => ({
		ts: NOW - (5 - index) * 86_400,
		rx: (index + 1) * 10 * GB,
		tx: (index + 1) * 2 * GB,
	})),
	rx_total: 150 * GB,
	tx_total: 30 * GB,
	top_days: [
		{ date: "2026-10-12", ts: 1_791_000_000, ...vol(80 * GB, 20 * GB) },
		{ date: "2026-10-05", ts: 1_790_500_000, ...vol(30 * GB, 5 * GB) },
	],
	hour_profile: hours,
	...over,
});

const SERVERS = [server(1, "de-1", "exit", "DE", 60, 3), server(2, "ir-1", "relay", "IR", 40, 1)];

type Mocks = {
	summary?: TrafficSummary;
	series?: (query: URLSearchParams) => TrafficSeries;
	links?: unknown[];
};

function open(entry: string, mocks: Mocks = {}) {
	const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
		const url = new URL(String(input), "http://localhost");
		const path = url.pathname.replace(/^.*\/api\/v1/, "");
		const body: unknown =
			path === "/auth/me"
				? user
				: path === "/traffic/summary"
					? (mocks.summary ?? summary(SERVERS))
					: path === "/traffic/series"
						? (mocks.series ?? (() => series()))(url.searchParams)
						: path === "/links/traffic"
							? { since: 0, until: 1, links: mocks.links ?? [] }
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
	const calls = (path: string) =>
		fetchMock.mock.calls
			.map(([input]) => new URL(String(input), "http://localhost"))
			.filter((url) => url.pathname.endsWith(path));
	return { router, calls };
}

const tile = (tiles: HTMLElement, label: string) =>
	within(within(tiles).getByText(label).parentElement?.parentElement as HTMLElement);

const choose = async (field: string, option: string) => {
	const buttons = await screen.findAllByRole("button", { name: new RegExp(field) });
	const trigger = buttons.find((button) => !button.getAttribute("aria-label")?.startsWith("مرتب"));
	await userEvent.click(trigger as HTMLElement);
	await userEvent.click(await screen.findByRole("option", { name: option }));
};

describe("TrafficPage", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("shows today, yesterday, the period, the average and the peak day with the split", async () => {
		open("/traffic");
		const tiles = await screen.findByRole("region", { name: "خلاصهٔ ترافیک" });
		expect(tile(tiles, "امروز").getByText("۱۰ گیگابایت", { selector: "div" })).toBeTruthy();
		expect(tile(tiles, "دیروز").getByText("۱٫۲ ترابایت", { selector: "div" })).toBeTruthy();
		expect(tile(tiles, "مجموع بازه").getByText("۱٬۰۰۰ گیگابایت", { selector: "div" })).toBeTruthy();
		expect(tile(tiles, "مجموع بازه").getByText("۹۰۰ گیگابایت")).toBeTruthy();
		expect(tile(tiles, "مجموع بازه").getByText("۱۰۰ گیگابایت")).toBeTruthy();
		expect(
			tile(tiles, "میانگین روزانه").getByText("۴۰ گیگابایت", { selector: "div" }),
		).toBeTruthy();
		expect(tile(tiles, "میانگین روزانه").getByText("میانگین ۲۵ روز دارای ترافیک")).toBeTruthy();
		expect(
			tile(tiles, "پرترافیک‌ترین روز").getByText("۱۰۰ گیگابایت", { selector: "div" }),
		).toBeTruthy();
	});

	it("asks for the 30 days that end today and draws the chart, hours and best days", async () => {
		const { calls } = open("/traffic");
		await screen.findByRole("region", { name: "خلاصهٔ ترافیک" });
		const [call] = calls("/traffic/series");
		const since = Number(call?.searchParams.get("since"));
		const until = Number(call?.searchParams.get("until"));
		expect(call?.searchParams.get("tz_offset_min")).toBe("210");
		expect((until - since) / 86_400).toBe(30);
		expect(await screen.findByText("هر نقطه یک روز است.")).toBeTruthy();
		expect(screen.getByText("پرترافیک‌ترین ساعت ۲۱:۰۰ با میانگین ۵٫۵ گیگابایت")).toBeTruthy();
		const days = screen.getByRole("region", { name: "ده روز پرترافیک این بازه" });
		expect(within(days).getAllByRole("row")).toHaveLength(3);
		expect(within(days).getByText("۱۰۰ گیگابایت")).toBeTruthy();
	});

	it("lists every server with its volumes, a link to its page and its share", async () => {
		open("/traffic");
		const table = await screen.findByRole("grid", { name: "ترافیک هر سرور در بازهٔ انتخاب‌شده" });
		const rows = within(table).getAllByRole("row");
		expect(rows).toHaveLength(3);
		const first = rows[1] as HTMLElement;
		const link = within(first).getByRole("link", { name: "de-1" });
		expect(link.getAttribute("href")).toBe("/servers/1");
		expect(within(first).getByText("🇩🇪")).toBeTruthy();
		expect(within(first).getByText("۶۰٪")).toBeTruthy();
		expect(within(first).getByText("نود")).toBeTruthy();
		expect(within(first).getAllByText("۳۰۰ گیگابایت").length).toBeGreaterThan(0);
	});

	it("sorts by a column and flips it on the second press", async () => {
		open("/traffic");
		const table = await screen.findByRole("grid", { name: "ترافیک هر سرور در بازهٔ انتخاب‌شده" });
		const names = () =>
			within(table)
				.getAllByRole("link")
				.map((link) => link.textContent);
		expect(names()).toEqual(["de-1", "ir-1"]);
		await userEvent.click(within(table).getByRole("button", { name: "مرتب‌سازی بر اساس سرور" }));
		expect(names()).toEqual(["de-1", "ir-1"]);
		await userEvent.click(within(table).getByRole("button", { name: "مرتب‌سازی بر اساس سرور" }));
		expect(names()).toEqual(["ir-1", "de-1"]);
	});

	it("filters the table by name and by role", async () => {
		open("/traffic");
		const table = await screen.findByRole("grid", { name: "ترافیک هر سرور در بازهٔ انتخاب‌شده" });
		await userEvent.type(screen.getByRole("searchbox", { name: "جستجوی سرور" }), "ir-");
		await waitFor(() => expect(within(table).queryByRole("link", { name: "de-1" })).toBeNull());
		expect(within(table).getByRole("link", { name: "ir-1" })).toBeTruthy();
		await userEvent.clear(screen.getByRole("searchbox", { name: "جستجوی سرور" }));
		await choose("نقش", "نود");
		await waitFor(() => expect(within(table).queryByRole("link", { name: "ir-1" })).toBeNull());
		expect(within(table).getByRole("link", { name: "de-1" })).toBeTruthy();
	});

	it("asks for the chosen period and keeps it in the address", async () => {
		const { router, calls } = open("/traffic");
		await screen.findByRole("region", { name: "خلاصهٔ ترافیک" });
		await choose("بازهٔ زمانی", "ماه شمسی جاری");
		await waitFor(() => expect(router.state.location.search).toMatchObject({ period: "jmonth" }));
		await waitFor(() => {
			const last = calls("/traffic/summary").at(-1) as URL;
			const days =
				(Number(last.searchParams.get("until")) - Number(last.searchParams.get("since"))) / 86_400;
			expect(days).toBeGreaterThanOrEqual(29);
			expect(days).toBeLessThanOrEqual(31);
		});
	});

	it("shows one server's numbers and curve when it is chosen, and keeps it in the address", async () => {
		const { router, calls } = open("/traffic");
		await screen.findByRole("region", { name: "خلاصهٔ ترافیک" });
		await choose("سرور", "🇮🇷 ir-1");
		await waitFor(() => expect(router.state.location.search).toMatchObject({ server: 2 }));
		await waitFor(() =>
			expect(calls("/traffic/series").at(-1)?.searchParams.get("server_id")).toBe("2"),
		);
		const tiles = screen.getByRole("region", { name: "خلاصهٔ ترافیک" });
		await waitFor(() =>
			expect(tile(tiles, "دیروز").getByText("۲۰ گیگابایت", { selector: "div" })).toBeTruthy(),
		);
		expect(tile(tiles, "امروز").getByText("۱۰ گیگابایت", { selector: "div" })).toBeTruthy();
	});

	it("opens on the server and range in the address", async () => {
		const { calls } = open("/traffic?period=custom&from=2026-10-01&to=2026-10-31&server=1");
		await screen.findByRole("region", { name: "خلاصهٔ ترافیک" });
		const call = calls("/traffic/series")[0];
		expect(call?.searchParams.get("server_id")).toBe("1");
		expect(Number(call?.searchParams.get("until")) - Number(call?.searchParams.get("since"))).toBe(
			31 * 86_400,
		);
		expect(screen.getByText("از تاریخ")).toBeTruthy();
		expect(screen.getByText("تا تاریخ")).toBeTruthy();
		expect(screen.getByText(/فقط تاریخ حساب می‌شود/)).toBeTruthy();
	});

	it("does not ask when a custom range is wrong", async () => {
		const { calls } = open("/traffic?period=custom&from=2026-10-31&to=2026-10-01");
		expect(await screen.findByText(/بازه درست نیست/)).toBeTruthy();
		expect(calls("/traffic/summary")).toHaveLength(0);
		expect(calls("/traffic/series")).toHaveLength(0);
	});

	it("says so when there is no traffic or no server", async () => {
		open("/traffic", {
			summary: summary([]),
			series: () =>
				series({
					points: [],
					rx_total: 0,
					tx_total: 0,
					top_days: [],
					hour_profile: hours.map((h) => ({ ...h, rx: 0, tx: 0 })),
				}),
		});
		expect(await screen.findByText("سروری پیدا نشد")).toBeTruthy();
		expect((await screen.findAllByText("در این بازه داده‌ای ثبت نشده است.")).length).toBeGreaterThan(
			0,
		);
		expect(screen.getByText("در این بازه روزی با ترافیک ثبت نشده است.")).toBeTruthy();
		expect(screen.getAllByText("در این بازه ترافیکی ثبت نشده است.").length).toBeGreaterThan(0);
	});

	it("lists the bytes between a relay and each exit", async () => {
		const link = {
			server_id: 7,
			server_name: "رلهٔ آزمایشی",
			server_role: "relay",
			peer_ip: "198.51.100.20",
			peer_id: 1,
			peer_name: "خروجی آزمایشی",
			peer_role: "exit",
			in_bytes: 3_000_000_000,
			out_bytes: 1_000_000_000,
		};
		open("/traffic", { links: [link] });
		expect(await screen.findByText("رلهٔ آزمایشی")).toBeTruthy();
		expect(screen.getByText("خروجی آزمایشی")).toBeTruthy();
		expect(screen.getByText("198.51.100.20")).toBeTruthy();
	});

	it("says how to switch counting on when no link has data", async () => {
		open("/traffic");
		expect(await screen.findByText(t.traffic.links.emptyTitle)).toBeTruthy();
	});
});
