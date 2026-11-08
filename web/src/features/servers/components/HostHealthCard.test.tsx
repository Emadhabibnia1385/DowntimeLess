import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { HostHealth } from "@/api/generated/model";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";
import { hostHealthFixture } from "@/test/checksFixtures";
import { healthRows } from "../lib/hostHealth";

const NOW = Math.floor(Date.now() / 1000);
const server = {
	id: 1,
	name: "ir-1",
	alias: "",
	role: "relay",
	status: "online",
	permission: "full",
	agent_version: "0.3.1",
	agent_outdated: false,
	category_id: null,
	country: "IR",
	city: null,
	org: null,
	hostname: "ir-1",
	public_ip: "203.0.113.9",
	last_seen: NOW - 10,
	acct_on: true,
	quota_gb: null,
	quota_reset_day: null,
	system: { os: null, kernel: null, cpu_model: null, cpu_cores: 2, boot_ts: null, ipv6: null },
	latest: { cpu_pct: 10, cpu_cores: 2, failed_units: [], reboot_required: false },
};

type Call = { method: string; url: string; body: unknown };

function open(health: HostHealth, role = "owner") {
	const calls: Call[] = [];
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
			const url = String(input);
			const method = init?.method ?? "GET";
			calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
			const path = url.replace(/^.*\/api\/v1/, "").replace(/\?.*$/, "");
			const body: unknown =
				path === "/auth/me"
					? {
							id: 1,
							name: "T",
							username: null,
							role,
							has_password: false,
							workspace: { id: 1, name: "فضای کار اصلی", role, is_personal: true },
							tg_username: null,
						}
					: path === "/servers/1"
						? server
						: path === "/servers/1/host-health" || path === "/servers/1/listeners"
							? health
							: path === "/servers/1/metrics"
								? { points: [], range: "24h", rx_total: 0, tx_total: 0 }
								: path === "/traffic/summary"
									? {
											generated_at: NOW,
											tz_offset_min: 210,
											since: NOW - 86_400,
											until: NOW,
											fleet: {},
											servers: [],
										}
									: [];
			return new Response(JSON.stringify(body), {
				status: 200,
				headers: { "Content-Type": "application/json" },
			});
		}),
	);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: ["/servers/1"] }),
	});
	render(
		<AppProviders
			queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
			router={router}
		/>,
	);
	return calls;
}

const card = () => screen.findByRole("region", { name: "سلامت میزبان" });
const rowOf = (table: HTMLElement, label: string) =>
	within(table)
		.getAllByRole("row")
		.find((row) => within(row).queryByText(label)) as HTMLElement;

describe("healthRows", () => {
	it("names the missing port, the stopped tunnel and the stopped container", () => {
		const rows = Object.fromEntries(healthRows(hostHealthFixture()).map((row) => [row.key, row]));
		expect(rows.listeners.tone).toBe("danger");
		expect(rows.listeners.detail).toContain("tcp/443 (xray)");
		expect(rows.units.tone).toBe("danger");
		expect(rows.units.detail).toContain("backhaul-de.service");
		expect(rows.units.detail).not.toContain("nginx");
		expect(rows.containers.detail).toContain("panel-old");
		expect(rows.dnat.tone).toBe("success");
		expect(rows.conntrack.tone).toBe("warning"); // the 5-day default timeout
		expect(rows.kernel.tone).toBe("success");
	});

	it("leaves out what the agent did not send and is calm when all is well", () => {
		const rows = healthRows(
			hostHealthFixture({
				listeners: { current: 5, baseline: 5, learning: 0, missing: [] },
				units: null,
				containers: [],
				conntrack: null,
				nft: { relay_dnat: false, dnat_rules: 0, tables: 0, ip_forward: 1, had_dnat: true },
			}),
		);
		expect(rows.map((row) => row.key)).toEqual([
			"listeners",
			"containers",
			"dnat",
			"kernel",
			"security",
		]);
		expect(rows[0].tone).toBe("success");
		expect(rows.find((row) => row.key === "dnat")?.tone).toBe("danger"); // it had DNAT and lost it
	});
});

describe("HostHealthCard", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("shows the checks as a table and lets an admin drop a port from the baseline", async () => {
		const calls = open(hostHealthFixture());
		const region = await card();
		const table = within(region).getByRole("region", { name: "جدول سلامت میزبان" });
		expect(within(rowOf(table, "لیسنرها")).getByText("مشکل")).toBeTruthy();
		expect(within(rowOf(table, "سرویس‌های تانل")).getByText(/backhaul-de\.service/)).toBeTruthy();
		expect(within(rowOf(table, "conntrack زنده")).getByText("توجه")).toBeTruthy();
		await userEvent.click(within(region).getByRole("button", { name: "حذف tcp/443 از خط پایه" }));
		await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true), {
			timeout: 3000,
		});
		expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ proto: "tcp", port: 443 });
		expect(
			within(region).getByRole("button", { name: "بازنشسته کردن کانتینر panel-old" }),
		).toBeTruthy();
	});

	it("tells a viewer what it sees but offers no actions", async () => {
		open(hostHealthFixture(), "viewer");
		const region = await card();
		await within(region).findByRole("region", { name: "جدول سلامت میزبان" });
		expect(within(region).queryByRole("button")).toBeNull();
	});

	it("explains a server whose agent sends no checks", async () => {
		open(hostHealthFixture({ has_checks: false, listeners: null, units: null, containers: null }));
		const region = await card();
		expect(within(region).getByText(/نسخهٔ قدیمی‌تر از ۰٫۳/)).toBeTruthy();
	});
});
