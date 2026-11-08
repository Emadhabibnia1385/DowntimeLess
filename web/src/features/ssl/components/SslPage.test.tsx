import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";
import type { SslRow } from "@/api/generated/model";

const NOW = Math.floor(Date.now() / 1000);

const row = (over: Partial<SslRow>): SslRow => ({
	key: "s1:a",
	kind: "file",
	source: "certbot",
	server_id: 1,
	server_name: "de-1",
	name: "a.example.com",
	domains: ["a.example.com"],
	not_after: NOW + 86_400 * 60,
	days_left: 60,
	issuer: null,
	error: null,
	auto_renew: "on",
	renew_failed: false,
	level: "ok",
	checked_at: NOW,
	stale: false,
	auto: false,
	can_renew: true,
	can_delete: true,
	...over,
});

const ROWS: SslRow[] = [
	row({
		key: "s1:vpn",
		name: "vpn.example.com",
		domains: ["vpn.example.com", "sub.example.com"],
		days_left: 3,
		level: "critical",
		auto_renew: "off",
		renew_failed: true,
		stale: true,
	}),
	row({ key: "s2:gone", name: "gone.example.com", days_left: -2, level: "critical" }),
	row({
		key: "d1",
		kind: "probe",
		source: "probe",
		server_id: null,
		server_name: null,
		name: "probe.example.org",
		domains: ["probe.example.org"],
		days_left: 20,
		level: "warning",
		auto_renew: "unknown",
		issuer: "Let's Encrypt",
		id: 1,
		can_renew: false,
	}),
	row({ key: "ok", name: "ok.example.com" }),
];

const user = {
	id: 1,
	name: "T",
	username: null,
	role: "owner",
	has_password: false,
	tg_username: null,
};

function answer(url: string, rows: SslRow[]): Response {
	const body = url.endsWith("/auth/me") ? user : url.endsWith("/ssl") ? rows : [];
	return new Response(JSON.stringify(body), {
		status: 200,
		headers: { "Content-Type": "application/json" },
	});
}

async function open(rows: SslRow[]) {
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL) => answer(String(input), rows)),
	);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: ["/ssl"] }),
	});
	const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
	render(<AppProviders queryClient={queryClient} router={router} />);
	return screen.findByRole("heading", { level: 1, name: "گواهی‌های SSL" });
}

describe("SslPage", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("shows each certificate with its status in words, where it lives and its renewal", async () => {
		await open(ROWS);
		const table = await screen.findByRole("grid", { name: "فهرست گواهی‌ها" });
		const line = (name: string) =>
			within(table)
				.getAllByRole("row")
				.find((r) => within(r).queryByText(name)) as HTMLElement;
		expect(within(table).getAllByRole("row").slice(1)).toHaveLength(4);
		const vpn = line("vpn.example.com");
		expect(within(vpn).getByText("۳ روز مانده")).toBeTruthy();
		expect(within(vpn).getByText("sub.example.com")).toBeTruthy();
		expect(within(vpn).getByRole("link", { name: "روی de-1" })).toBeTruthy();
		expect(within(vpn).getByText("غیرفعال")).toBeTruthy();
		expect(within(vpn).getByText("آخرین تمدید ناموفق")).toBeTruthy();
		expect(within(vpn).getByText("اطلاعات قدیمی: سرور آفلاین است")).toBeTruthy();
		expect(within(line("gone.example.com")).getByText("منقضی شده")).toBeTruthy();
		const probe = line("probe.example.org");
		expect(within(probe).getByText("بررسی از بیرون")).toBeTruthy();
		expect(within(probe).getByText("نامشخص (فقط بررسی بیرونی)")).toBeTruthy();
		expect(within(line("ok.example.com")).getByText("سالم")).toBeTruthy();
	});

	it("offers a renew and a delete for a certbot certificate and a re-check and delete for a probe", async () => {
		await open(ROWS);
		const table = await screen.findByRole("grid", { name: "فهرست گواهی‌ها" });
		const line = (name: string) =>
			within(table)
				.getAllByRole("row")
				.find((r) => within(r).queryByText(name)) as HTMLElement;
		const vpn = line("vpn.example.com");
		expect(within(vpn).getByRole("button", { name: "تمدید همین حالا" })).toBeTruthy();
		expect(within(vpn).getByRole("button", { name: "حذف گواهی از روی سرور" })).toBeTruthy();
		const probe = line("probe.example.org");
		expect(within(probe).getByRole("button", { name: "بررسی دوباره" })).toBeTruthy();
		expect(within(probe).getByRole("button", { name: "حذف" })).toBeTruthy();
		expect(within(probe).queryByRole("button", { name: "تمدید همین حالا" })).toBeNull();
	});

	it("lists the soonest to expire first and has a sort button on each sortable column", async () => {
		await open(ROWS);
		const table = await screen.findByRole("grid", { name: "فهرست گواهی‌ها" });
		const first = within(table).getAllByRole("row")[1];
		expect(within(first).queryAllByText("gone.example.com")).toHaveLength(1);
		for (const label of ["گواهی", "محل", "وضعیت", "تاریخ انقضا", "تمدید خودکار"]) {
			expect(screen.getByRole("button", { name: `مرتب‌سازی بر اساس ${label}` })).toBeTruthy();
		}
	});

	it("shows only one state of certificate when a filter is chosen, and narrows by typed text", async () => {
		await open(ROWS);
		const table = await screen.findByRole("grid", { name: "فهرست گواهی‌ها" });
		const count = () => within(table).getAllByRole("row").slice(1).length;
		await userEvent.click(screen.getByRole("radio", { name: "بحرانی یا منقضی" }));
		expect(count()).toBe(2);
		await userEvent.click(screen.getByRole("radio", { name: "سالم" }));
		expect(count()).toBe(1);
		await userEvent.click(screen.getByRole("radio", { name: "همه" }));
		await userEvent.type(screen.getByRole("searchbox", { name: "جست‌وجوی دامنه یا سرور" }), "probe");
		expect(count()).toBe(1);
	});

	it("marks a domain an agent found on its own", async () => {
		await open([
			...ROWS,
			row({
				key: "d9",
				kind: "probe",
				source: "probe",
				name: "found.example.com",
				domains: ["found.example.com"],
				auto: true,
				id: 9,
				can_renew: false,
				auto_renew: "unknown",
			}),
		]);
		const table = await screen.findByRole("grid", { name: "فهرست گواهی‌ها" });
		const found = within(table)
			.getAllByRole("row")
			.find((r) => within(r).queryByText("found.example.com")) as HTMLElement;
		expect(within(found).getByText("کشف‌شده")).toBeTruthy();
	});

	it("explains where certificates come from when there are none", async () => {
		await open([]);
		expect(await screen.findByText("هنوز گواهی‌ای ثبت نشده")).toBeTruthy();
		expect(screen.getByText(/\/etc\/letsencrypt/)).toBeTruthy();
	});
});
