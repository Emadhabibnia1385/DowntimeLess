import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Issue } from "@/api/generated/model";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";
import { fixCommand, fixOf } from "./lib";

const base = { severity: "warning", title: "t", suggestion: "s", recent_24h: 0, acked: false };
const issues: Issue[] = [
	{
		...base,
		id: "server:5:drift_ipset",
		server_id: 5,
		server_name: "sepehr",
		code: "drift_ipset",
		title: "ipset",
		evidence: { live: 8, file: 21 },
	},
	{
		...base,
		id: "server:6:tunnel_unhealthy:de1",
		server_id: 6,
		server_name: "de-1",
		code: "tunnel_unhealthy:de1",
		title: "tunnel",
		evidence: { unit: "backpack-de1.service" },
	},
	{
		...base,
		id: "server:7:disk",
		server_id: 7,
		server_name: "fi-1",
		code: "disk",
		title: "disk",
		evidence: { disk_pct: 91 },
	},
];

function open(role: string) {
	const posted: { path: string; body: unknown }[] = [];
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
			const url = new URL(String(input), "http://localhost");
			const route = url.pathname.replace(/^.*\/api\/v1/, "");
			if (init?.method === "POST") {
				posted.push({ path: route, body: JSON.parse(String(init.body)) });
				return new Response(
					JSON.stringify({
						id: 1,
						kind: "x",
						args: {},
						status: "queued",
						result: null,
						error: null,
						created_at: 1,
						done_at: null,
					}),
					{ status: 201, headers: { "Content-Type": "application/json" } },
				);
			}
			const me = {
				id: 1,
				name: "T",
				username: null,
				role,
				has_password: false,
				tg_username: null,
				workspace: { id: 1, name: "اصلی", role, is_personal: true },
			};
			const body: unknown = route === "/auth/me" ? me : route === "/issues" ? issues : [];
			return new Response(JSON.stringify(body), {
				status: 200,
				headers: { "Content-Type": "application/json" },
			});
		}),
	);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: ["/issues"] }),
	});
	render(
		<AppProviders
			queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
			router={router}
		/>,
	);
	return posted;
}

describe("one-click fixes", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("maps only the matching alerts to a fix and shows the exact command", () => {
		expect(fixOf(issues[0])).toEqual({ kind: "ipset_sync", args: {} });
		expect(fixOf(issues[1])).toEqual({
			kind: "tunnel_restart",
			args: { unit: "backpack-de1.service" },
		});
		expect(fixOf(issues[2])).toBeNull();
		expect(fixOf({ ...issues[1], evidence: { unit: "nginx.service" } })).toBeNull();
		expect(fixOf({ ...issues[0], server_id: null })).toBeNull();
		expect(fixCommand({ kind: "tunnel_restart", args: { unit: "backpack-de1.service" } })).toBe(
			"systemctl restart -- backpack-de1.service",
		);
	});

	it("lets an admin confirm a fix after reading the command, and queues it", async () => {
		const posted = open("admin");
		await userEvent.click(await screen.findByRole("button", { name: /^رفع «.*» روی sepehr$/ }));
		const dialog = await screen.findByRole("alertdialog");
		expect(within(dialog).getByText(/systemctl restart -- nyxon-access.service/)).toBeTruthy();
		expect(posted).toEqual([]);
		await userEvent.click(within(dialog).getByRole("button", { name: "تأیید و فرستادن به سرور" }));
		await waitFor(() =>
			expect(posted).toEqual([{ path: "/servers/5/jobs", body: { kind: "ipset_sync", args: {} } }]),
		);
		expect(screen.getByRole("button", { name: /^رفع «.*» روی de-1$/ })).toBeTruthy();
		expect(screen.queryByRole("button", { name: /^رفع «.*» روی fi-1$/ })).toBeNull();
	});

	it("shows no fix button to an operator or a viewer", async () => {
		open("operator");
		expect(await screen.findByText("sepehr")).toBeTruthy();
		expect(screen.queryByRole("button", { name: /^رفع «/ })).toBeNull();
	});
});
