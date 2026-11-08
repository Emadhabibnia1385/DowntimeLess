import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
	FleetHistory,
	Issue,
	IssuesHistory,
	Overview,
	PingCell,
	ServerOut,
	SslRow,
} from "@/api/generated/model";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

const NOW = Math.floor(Date.now() / 1000);
const GIB = 1024 ** 3;

const user = {
	id: 1,
	name: "T",
	username: null,
	role: "owner",
	has_password: false,
	workspace: { id: 1, name: "فضای کار اصلی", role: "owner", is_personal: true },
	tg_username: null,
};

const server = (id: number, name: string, over: Partial<ServerOut> = {}): ServerOut => ({
	id,
	name,
	alias: "",
	role: "exit",
	status: "online",
	permission: "read",
	agent_version: "0.2.7",
	category_id: null,
	country: "DE",
	city: null,
	org: null,
	hostname: null,
	public_ip: null,
	last_seen: NOW,
	latest: { cpu_pct: 20, ram_pct: 50, disk_pct: 30, rx_bps: 2_000_000, tx_bps: 1_000_000 },
	...over,
});

const servers = [
	server(1, "de-1", { latest: { cpu_pct: 20, ram_pct: 50, disk_pct: 30, rx_bps: 9_000_000 } }),
	server(2, "nl-2", { country: "NL", latest: { cpu_pct: 60, ram_pct: 70, disk_pct: 95 } }),
	server(3, "fr-3", { country: "FR", latest: { cpu_pct: 40, ram_pct: 60, disk_pct: 40 } }),
	server(4, "ir-4", { status: "offline", country: "IR", latest: { cpu_pct: 99, ram_pct: 99 } }),
];

const overview: Overview = {
	servers_total: 4,
	online: 3,
	offline: 1,
	pending: 2,
	issues_critical: 1,
	issues_warning: 2,
	rx_bytes_24h: 0,
	tx_bytes_24h: 0,
};

const issue = (id: string, severity: string, over: Partial<Issue> = {}): Issue => ({
	id,
	server_id: 1,
	server_name: "de-1",
	code: "disk",
	severity,
	title: "دیسک رو به پر شدن است",
	suggestion: "پاک‌سازی",
	evidence: {},
	recent_24h: 0,
	...over,
});

const issues = [
	issue("a", "warning", { title: "مصرف RAM بالاست" }),
	issue("b", "info", { title: "نیاز به ریبوت", server_id: 3, server_name: "fr-3" }),
	issue("c", "critical", { server_id: 2, server_name: "nl-2" }),
	issue("d", "warning", { title: "مصرف CPU بالاست", server_id: 3, server_name: "fr-3" }),
];

const history = (range: string): FleetHistory => ({
	range,
	rx_total: 5 * GIB,
	tx_total: 2 * GIB,
	points: Array.from({ length: 30 }, (_, index) => ({
		ts: NOW - (30 - index) * 300,
		rx_bytes: 1_000_000 * (index + 1),
		tx_bytes: 500_000 * (index + 1),
		cpu: 20 + index,
		ram_pct: 50,
		disk_pct: 40,
		servers: 3,
	})),
});

const issuesHistory = (): IssuesHistory => ({
	range: "24h",
	since: NOW - 86_400,
	summary: [
		{
			key: "a",
			code: "ram",
			server_id: 1,
			server_name: "de-1",
			title: "مصرف RAM بالاست",
			severity: "warning",
			occurrences: 7,
			total_s: 3600,
			last_at: NOW - 60,
			active_now: true,
			flapping: true,
			evidence: {},
		},
		{
			key: "x",
			code: "cpu",
			server_id: 2,
			server_name: "nl-2",
			title: "مصرف CPU بالاست",
			severity: "warning",
			occurrences: 1,
			total_s: 60,
			last_at: NOW - 600,
			active_now: false,
			flapping: false,
			evidence: {},
		},
	],
	incidents: [
		{
			id: 1,
			key: "c",
			code: "disk",
			server_id: 2,
			server_name: "nl-2",
			severity: "critical",
			title: "دیسک رو به پر شدن است",
			opened_at: NOW - 3 * 3600 - 30,
			closed_at: null,
			duration_s: 0,
		},
	],
	totals: { occurrences: 8, issues: 2, active_now: 1, critical: 1 },
});

const cert = (key: string, name: string, days: number | null, level: string): SslRow => ({
	key,
	name,
	domains: [name],
	days_left: days,
	level,
	error: null,
	checked_at: NOW,
	not_after: days === null ? null : NOW + days * 86_400,
	issuer: null,
	auto_renew: "on",
	renew_failed: false,
	server_id: null,
	server_name: null,
	source: "probe",
	kind: "domain",
	stale: false,
});

const certs = [
	cert("1", "ok.example.com", 80, "ok"),
	cert("2", "soon.example.com", 12, "warning"),
	cert("3", "late.example.com", 2, "critical"),
];

const ping = (to: number, name: string, loss: number | null, rtt: number | null): PingCell => ({
	from_id: 9,
	from_name: "ir-9",
	to_id: to,
	to_name: name,
	target: "10.0.0.1",
	loss_pct: loss,
	rtt_ms: rtt,
	ts: NOW,
});

const pings = [ping(1, "de-1", 0, 41), ping(2, "nl-2", 60, 120), ping(3, "fr-3", 12, 80)];

type Data = {
	servers: ServerOut[];
	issues: Issue[];
	certs: SslRow[];
	pings: PingCell[];
	history: (range: string) => FleetHistory;
	issuesHistory: IssuesHistory;
};

const full: Data = { servers, issues, certs, pings, history, issuesHistory: issuesHistory() };
const empty: Data = {
	servers: [],
	issues: [],
	certs: [],
	pings: [],
	history: (range) => ({ range, points: [], rx_total: 0, tx_total: 0 }),
	issuesHistory: { ...issuesHistory(), summary: [], incidents: [] },
};

function open(entry: string, data: Data = full) {
	const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
		const url = new URL(String(input), "http://localhost");
		const path = url.pathname.replace(/^.*\/api\/v1/, "");
		const bodies: Record<string, unknown> = {
			"/auth/me": user,
			"/overview": { ...overview, servers_total: data.servers.length ? 4 : 0 },
			"/overview/history": data.history(url.searchParams.get("range") ?? "24h"),
			"/servers": data.servers,
			"/issues": data.issues,
			"/issues/history": data.issuesHistory,
			"/ssl": data.certs,
			"/ping-matrix": data.pings,
			"/settings": {},
			"/traffic/summary": {
				fleet: {
					today: { rx: 3 * GIB, tx: GIB, total: 4 * GIB },
					yesterday: { rx: 6 * GIB, tx: 2 * GIB, total: 8 * GIB },
				},
				servers: [],
			},
		};
		return new Response(JSON.stringify(bodies[path] ?? []), {
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
	const calls = (part: string) =>
		fetchMock.mock.calls.map(([input]) => String(input)).filter((url) => url.includes(part));
	return { router, calls };
}

const tile = (label: string) => {
	const stats = screen.getByRole("region", { name: "آمار ناوگان" });
	return within(stats).getByText(label).parentElement?.parentElement as HTMLElement;
};

describe("DashboardPage", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("computes the eight tiles from the data", async () => {
		open("/");
		await screen.findByRole("region", { name: "آمار ناوگان" });
		await waitFor(() => expect(within(tile("سرورهای آنلاین")).getByText("۳ از ۴")).toBeTruthy());
		expect(within(tile("سرورهای آنلاین")).getByText("۱ آفلاین، ۲ نصب‌نشده")).toBeTruthy();
		await waitFor(() => expect(within(tile("مشکل‌های باز")).getByText("۴")).toBeTruthy());
		expect(within(tile("مشکل‌های باز")).getByText("۱ بحرانی، ۲ هشدار، ۱ اطلاع")).toBeTruthy();
		await waitFor(() => expect(within(tile("ترافیک امروز")).getByText("۴")).toBeTruthy());
		expect(within(tile("ترافیک امروز")).getByText("گیگابایت · دیروز ۸ گیگابایت")).toBeTruthy();
		await waitFor(() => expect(within(tile("ترافیک بازه")).getByText("۷")).toBeTruthy());
		expect(
			within(tile("ترافیک بازه")).getByText(
				"گیگابایت · دانلود ۵ گیگابایت، آپلود ۲ گیگابایت · ۲۴ ساعت اخیر",
			),
		).toBeTruthy();
		await waitFor(() => expect(within(tile("گواهی در خطر")).getByText("۲")).toBeTruthy());
		expect(within(tile("گواهی در خطر")).getByText("۱ بحرانی از ۳ گواهی")).toBeTruthy();
		// The offline server (99%) is left out: (20 + 60 + 40) / 3 and (50 + 70 + 60) / 3.
		await waitFor(() => expect(within(tile("میانگین CPU")).getByText("۴۰٪")).toBeTruthy());
		expect(within(tile("میانگین CPU")).getByText("روی ۳ سرور آنلاین")).toBeTruthy();
		expect(within(tile("میانگین RAM")).getByText("۶۰٪")).toBeTruthy();
		await waitFor(() => expect(within(tile("بدترین مسیر پینگ")).getByText("۶۰٪")).toBeTruthy());
		expect(within(tile("بدترین مسیر پینگ")).getByText("ir-9 به nl-2")).toBeTruthy();
	});

	it("opens on 24 hours and asks the master for the chosen range", async () => {
		const { router, calls } = open("/?range=7d");
		await screen.findByRole("region", { name: "آمار ناوگان" });
		await waitFor(() => expect(calls("/overview/history").length).toBeGreaterThan(0));
		expect(calls("/overview/history").every((url) => url.includes("range=7d"))).toBe(true);
		await userEvent.click(screen.getByRole("radio", { name: "۳۰ روز" }));
		await waitFor(() =>
			expect(calls("/overview/history").some((url) => url.includes("range=30d"))).toBe(true),
		);
		expect(router.state.location.search).toMatchObject({ range: "30d" });
		await waitFor(() => expect(within(tile("ترافیک بازه")).getByText(/۳۰ روز اخیر/)).toBeTruthy());
	});

	it("falls back to 24 hours for a range the page does not offer", async () => {
		const { calls } = open("/?range=1h");
		await waitFor(() => expect(calls("/overview/history").length).toBeGreaterThan(0));
		expect(calls("/overview/history")[0]).toContain("range=24h");
	});

	it("switches the history tab", async () => {
		open("/");
		await userEvent.click(await screen.findByRole("radio", { name: "مصرف (درصد)" }));
		expect(await screen.findByText(/میانگین مصرف پردازنده/)).toBeTruthy();
	});

	it("lists the busiest online servers by CPU with links to their pages", async () => {
		open("/");
		const table = await screen.findByRole("region", { name: "جدول پرمصرف‌ترین سرورها" });
		const links = within(table).getAllByRole("link");
		expect(links.map((link) => link.textContent)).toEqual(["nl-2", "fr-3", "de-1"]);
		expect(links[0].getAttribute("href")).toBe("/servers/2");
		expect(within(table).getByText("🇳🇱")).toBeTruthy();
		expect(within(table).getByText("۹۵٪")).toBeTruthy();
		expect(within(table).queryByText("ir-4")).toBeNull();
	});

	it("re-ranks the servers by traffic from the select", async () => {
		open("/");
		const table = await screen.findByRole("region", { name: "جدول پرمصرف‌ترین سرورها" });
		await userEvent.click(screen.getByRole("button", { name: /مرتب‌سازی/ }));
		await userEvent.click(await screen.findByRole("option", { name: "بیشترین ترافیک" }));
		await waitFor(() =>
			expect(
				within(table)
					.getAllByRole("link")
					.map((link) => link.textContent),
			).toEqual(["de-1", "nl-2", "fr-3"]),
		);
	});

	it("shows at most eight servers", async () => {
		const many = Array.from({ length: 11 }, (_, index) => server(index + 1, `s-${index + 1}`));
		open("/", { ...full, servers: many });
		const table = await screen.findByRole("region", { name: "جدول پرمصرف‌ترین سرورها" });
		expect(within(table).getAllByRole("link")).toHaveLength(8);
	});

	it("lists the open issues worst first with how long the oldest has been open", async () => {
		open("/");
		const table = await screen.findByRole("region", { name: "جدول مشکل‌های باز" });
		await waitFor(() => expect(within(table).getByText("۳ ساعت")).toBeTruthy());
		const rows = within(table).getAllByRole("row").slice(1);
		expect(rows).toHaveLength(4);
		expect(within(rows[0]).getByText("بحرانی")).toBeTruthy();
		expect(within(rows[0]).getByRole("link", { name: "nl-2" }).getAttribute("href")).toBe(
			"/servers/2",
		);
		expect(within(rows[3]).getByText("اطلاع")).toBeTruthy();
	});

	it("leaves acknowledged issues out of the tile and the card, with a note and an ack button", async () => {
		const known = issue("e", "critical", { acked: true, ack_mode: "always", server_name: "ir-4" });
		open("/", { ...full, issues: [...issues, known] });
		const table = await screen.findByRole("region", { name: "جدول مشکل‌های باز" });
		await waitFor(() => expect(within(tile("مشکل‌های باز")).getByText("۴")).toBeTruthy());
		expect(within(tile("مشکل‌های باز")).getByText("۱ بحرانی، ۲ هشدار، ۱ اطلاع")).toBeTruthy();
		expect(within(table).getAllByRole("row").slice(1)).toHaveLength(4);
		expect(within(table).queryByText("ir-4")).toBeNull();
		expect(screen.getByText("۱ مشکل پذیرفته‌شده در صفحهٔ گزارشات")).toBeTruthy();
		expect(within(table).getAllByRole("button", { name: /^پذیرفتن/ })).toHaveLength(4);
	});

	it("lists the problems that came back in 24 hours", async () => {
		open("/");
		const table = await screen.findByRole("region", { name: "جدول مشکل‌های ناپایدار در ۲۴ ساعت" });
		const rows = within(table).getAllByRole("row").slice(1);
		expect(rows).toHaveLength(1);
		expect(within(rows[0]).getByText("۷ بار")).toBeTruthy();
		expect(within(rows[0]).getByRole("link", { name: "de-1" })).toBeTruthy();
	});

	it("lists the certificates closest to expiry and the worst ping links", async () => {
		open("/");
		const ssl = await screen.findByRole("region", { name: "جدول نزدیک‌ترین انقضای گواهی‌ها" });
		const names = within(ssl)
			.getAllByRole("rowheader")
			.map((cell) => cell.textContent);
		expect(names).toEqual(["late.example.com", "soon.example.com", "ok.example.com"]);
		expect(within(ssl).getByText("۲ روز مانده")).toBeTruthy();
		const links = await screen.findByRole("region", { name: "جدول بدترین مسیرهای پینگ" });
		const rows = within(links).getAllByRole("row").slice(1);
		expect(rows).toHaveLength(3);
		expect(within(rows[0]).getByText("قطع")).toBeTruthy();
		expect(within(rows[0]).getByRole("link", { name: "nl-2" }).getAttribute("href")).toBe(
			"/servers/2",
		);
		expect(within(rows[1]).getByText("ناپایدار")).toBeTruthy();
		expect(within(rows[2]).getByText("سالم")).toBeTruthy();
	});

	it("links each card to its full page", async () => {
		open("/");
		await screen.findByRole("region", { name: "جدول پرمصرف‌ترین سرورها" });
		for (const [name, href] of [
			["همهٔ سرورها", "/servers"],
			["همهٔ مشکل‌ها", "/issues"],
			["همهٔ گواهی‌ها", "/ssl"],
			["ماتریس پینگ", "/ping-matrix"],
		] as const) {
			const link = screen.getAllByRole("link", { name })[0];
			expect(link.getAttribute("href")).toContain(href);
		}
	});

	it("says so in every card when there is nothing to show", async () => {
		open("/", empty);
		expect(await screen.findByText("سرور آنلاینی نیست", { selector: "h2" })).toBeTruthy();
		expect(await screen.findByText("مشکلی پیدا نشد")).toBeTruthy();
		expect(await screen.findByText("مورد ناپایداری نیست")).toBeTruthy();
		expect(await screen.findByText("گواهی‌ای ثبت نشده", { selector: "h2" })).toBeTruthy();
		expect(await screen.findByText("پینگی اندازه‌گیری نشده", { selector: "h2" })).toBeTruthy();
		expect((await screen.findAllByText("در این بازه داده‌ای ثبت نشده است.")).length).toBeGreaterThan(
			0,
		);
		expect(screen.queryByRole("table")).toBeNull();
	});
});
