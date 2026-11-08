import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { MetricPoint, ServerOut } from "@/api/generated/model";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

const NOW = Math.floor(Date.now() / 1000);

const server = (over: Partial<ServerOut> = {}): ServerOut => ({
	id: 1,
	name: "de-1",
	alias: "",
	role: "exit",
	status: "online",
	permission: "read",
	agent_version: "0.2.6",
	agent_outdated: false,
	category_id: 7,
	country: "DE",
	city: "Falkenstein",
	org: "Hetzner Online GmbH",
	hostname: "de-1.example.net",
	public_ip: "203.0.113.5",
	last_seen: NOW - 20,
	system: {
		os: "Ubuntu 24.04",
		kernel: "6.8.0",
		cpu_model: "AMD EPYC",
		cpu_cores: 4,
		boot_ts: NOW - 86_400,
		ipv6: "2001:db8::5",
	},
	latest: {
		cpu_pct: 50,
		cpu_cores: 4,
		ram_pct: 40,
		ram_total_mb: 8192,
		ram_used_mb: 3276,
		disk_pct: 30,
		disk_total_gb: 80,
		disk_used_gb: 24,
		load1: 0.5,
		load5: 0.4,
		load15: 0.3,
		rx_bps: 2_000_000,
		tx_bps: 1_000_000,
		uptime_s: 90_000,
		failed_units: [],
		reboot_required: false,
	},
	...over,
});

const points: MetricPoint[] = Array.from({ length: 20 }, (_, index) => ({
	ts: NOW - (20 - index) * 60,
	cpu: 20 + index,
	ram_pct: 40,
	disk_pct: 30,
	rx_bps: 1_000_000,
	tx_bps: 500_000,
	rx_bytes: 1000,
	tx_bytes: 500,
}));

const GB = 1024 ** 3;
const volume = (rx: number, tx: number) => ({ rx, tx, total: rx + tx });
const trafficSummary = {
	generated_at: NOW,
	tz_offset_min: 210,
	since: NOW - 30 * 86_400,
	until: NOW,
	fleet: {},
	servers: [
		{
			server_id: 1,
			name: "de-1",
			role: "exit",
			today: volume(8 * GB, 2 * GB),
			yesterday: volume(16 * GB, 4 * GB),
			period: volume(400 * GB, 100 * GB),
			avg_per_day: volume(20 * GB, 5 * GB),
			active_days: 20,
			peak_day: { date: "2026-10-12", ...volume(40 * GB, 10 * GB) },
			share_pct: 60,
		},
	],
};

const user = {
	id: 1,
	name: "T",
	username: null,
	role: "owner",
	has_password: false,
	tg_username: null,
};

function answer(url: string, data: ServerOut): Response {
	const path = url.replace(/^.*\/api\/v1/, "").replace(/\?.*$/, "");
	const body: unknown =
		path === "/auth/me"
			? user
			: path === "/servers/1"
				? data
				: path === "/traffic/summary"
					? trafficSummary
					: path === "/servers/1/metrics"
						? { points, range: "24h", rx_total: 0, tx_total: 0 }
						: path === "/categories"
							? [{ id: 7, name: "اروپا", server_count: 1 }]
							: path === "/ssl"
								? [
										{
											key: "s1:a",
											server_id: 1,
											name: "a.example.com",
											days_left: 12,
											level: "warning",
											error: null,
											checked_at: NOW,
										},
									]
								: [];
	return new Response(JSON.stringify(body), {
		status: 200,
		headers: { "Content-Type": "application/json" },
	});
}

async function open(data: ServerOut) {
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL) => answer(String(input), data)),
	);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: ["/servers/1"] }),
	});
	const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
	render(<AppProviders queryClient={queryClient} router={router} />);
	return screen.findByRole("heading", { level: 1 });
}

describe("ServerDetailPage", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("names the server with its flag, status, role and category", async () => {
		const heading = await open(server());
		expect(heading.textContent).toContain("de-1");
		expect(heading.textContent).toContain("🇩🇪");
		expect(screen.getByText("آنلاین")).toBeTruthy();
		expect((await screen.findAllByText("اروپا")).length).toBeGreaterThan(0);
	});

	it("shows the details with a copy button for the IP and no permission level", async () => {
		await open(server());
		const details = await screen.findByRole("region", { name: "مشخصات" });
		expect(within(details).getByText("203.0.113.5")).toBeTruthy();
		expect(within(details).getAllByRole("button", { name: "کپی آدرس IP" })).toHaveLength(2);
		expect(within(details).getByText("Ubuntu 24.04")).toBeTruthy();
		expect(within(details).getByText("Hetzner")).toBeTruthy();
		expect(document.body.textContent).not.toContain("سطح دسترسی");
		expect(screen.queryByRole("radio", { name: /فقط خواندن/ })).toBeNull();
	});

	it("shows the live tiles with the busy cores", async () => {
		await open(server());
		const tiles = await screen.findByRole("region", { name: "وضعیت زنده" });
		expect(within(tiles).getByText("۲ از ۴")).toBeTruthy();
		expect(within(tiles).getByText("آپ‌تایم")).toBeTruthy();
	});

	it("offers the operations, each change behind a confirmation", async () => {
		await open(server());
		const ops = await screen.findByRole("region", { name: "عملیات" });
		for (const name of ["پینگ", "پورت TCP", "تست سرعت", "به‌روزرسانی امن", "ریبوت سرور"]) {
			expect(within(ops).getByRole("button", { name })).toBeTruthy();
		}
		await userEvent.click(within(ops).getByRole("button", { name: "ریبوت سرور" }));
		expect(await screen.findByRole("alertdialog")).toBeTruthy();
	});

	it("has the history tabs and the certificates of this server", async () => {
		await open(server());
		const history = await screen.findByRole("region", { name: "تاریخچه" });
		for (const name of ["مصرف (درصد)", "سرعت شبکه", "بار سیستم", "کیفیت شبکه", "اتصال‌ها"]) {
			expect(within(history).getByRole("radio", { name })).toBeTruthy();
		}
		expect(within(history).getByRole("radio", { name: "۲۴ ساعت" })).toBeTruthy();
		expect(await screen.findByText("a.example.com")).toBeTruthy();
		await userEvent.click(within(history).getByRole("radio", { name: "سرعت شبکه" }));
		expect(await within(history).findByText("حجم منتقل‌شده در هر نقطه")).toBeTruthy();
	});

	it("has a compact traffic card that links to the details of this server", async () => {
		await open(server());
		const card = await screen.findByRole("region", { name: "ترافیک این سرور" });
		expect(await within(card).findByText("۱۰ گیگابایت")).toBeTruthy();
		expect(within(card).getByText("۵۰۰ گیگابایت")).toBeTruthy();
		expect(within(card).getByText("۵۰ گیگابایت", { exact: false })).toBeTruthy();
		const link = within(card).getByRole("link", { name: "جزئیات ترافیک" });
		expect(link.getAttribute("href")).toBe("/traffic?server=1");
	});

	it("shows an Iran relay with the Iranian flag and no foreign provider", async () => {
		const heading = await open(server({ role: "relay" }));
		expect(heading.textContent).toContain("🇮🇷");
		const details = await screen.findByRole("region", { name: "مشخصات" });
		expect(within(details).getByText("Iran")).toBeTruthy();
	});
});
