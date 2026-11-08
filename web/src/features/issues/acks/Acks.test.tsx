import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Issue } from "@/api/generated/model";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";
import { splitAcked, untilText } from "./lib";

const me = (role: string) => ({
	id: 1,
	name: "T",
	username: null,
	role,
	has_password: false,
	workspace: { id: 1, name: "فضای کار اصلی", role, is_personal: true },
	tg_username: null,
});

const issue = (over: Partial<Issue> = {}): Issue => ({
	id: "server:1:cpu",
	server_id: 1,
	server_name: "de-1",
	code: "cpu",
	severity: "warning",
	title: "مصرف CPU بالاست",
	suggestion: "پردازش‌ها را ببینید",
	evidence: { cpu_pct: 95 },
	recent_24h: 1,
	acked: false,
	...over,
});

const known = issue({
	id: "server:2:disk",
	server_id: 2,
	server_name: "nl-2",
	code: "disk",
	title: "دیسک رو به پر شدن است",
	acked: true,
	acked_by: "عماد",
	ack_mode: "always",
	acked_until: null,
	ack_note: "دیسک جدید در راه است",
});

type Call = { method: string; path: string; search: string; body: unknown };

function open(role: string, issues: Issue[]) {
	const calls: Call[] = [];
	const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
		const url = new URL(String(input), "http://localhost");
		const path = url.pathname.replace(/^.*\/api\/v1/, "");
		const method = init?.method ?? "GET";
		calls.push({
			method,
			path,
			search: url.search,
			body: init?.body ? JSON.parse(String(init.body)) : null,
		});
		if (method === "DELETE") return new Response(null, { status: 204 });
		const body: unknown =
			path === "/auth/me"
				? me(role)
				: path === "/issues/ack"
					? {
							key: "server:1:cpu",
							mode: "24h",
							until: 1,
							note: null,
							severity: "warning",
							created_at: 1,
						}
					: path === "/issues"
						? issues
						: [];
		return new Response(JSON.stringify(body), {
			status: 200,
			headers: { "Content-Type": "application/json" },
		});
	});
	vi.stubGlobal("fetch", fetchMock);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: ["/issues"] }),
	});
	const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
	render(<AppProviders queryClient={queryClient} router={router} />);
	return calls;
}

describe("acknowledging issues", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("splits acknowledged issues off and says until when they hold", () => {
		const { open: loud, acked } = splitAcked([issue(), known]);
		expect(loud.map((i) => i.id)).toEqual(["server:1:cpu"]);
		expect(acked.map((i) => i.id)).toEqual(["server:2:disk"]);
		expect(untilText(known)).toBe("همیشه");
		expect(untilText({ ...known, ack_mode: "until_resolved" })).toBe("تا برطرف شدن مشکل");
	});

	it("acknowledges an issue through the dialog with the chosen duration and note", async () => {
		const calls = open("operator", [issue()]);
		await userEvent.click(
			await screen.findByRole("button", { name: "پذیرفتن «مصرف CPU بالا» روی de-1" }),
		);
		const dialog = await screen.findByRole("dialog");
		const first = within(dialog).getByRole("radio", { name: /تا برطرف شدن مشکل/ });
		expect((first as HTMLInputElement).checked).toBe(true);
		await userEvent.click(within(dialog).getByRole("radio", { name: /۲۴ ساعت/ }));
		await userEvent.type(within(dialog).getByRole("textbox"), "در جریانم");
		await userEvent.click(within(dialog).getByRole("button", { name: "پذیرفتن" }));
		await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
		const post = calls.find((c) => c.method === "POST");
		expect(post?.path).toBe("/issues/ack");
		expect(post?.body).toEqual({ key: "server:1:cpu", mode: "24h", note: "در جریانم" });
		expect(await screen.findByText("پذیرفته شد؛ این مشکل دیگر شمرده نمی‌شود.")).toBeTruthy();
	});

	it("lists acknowledged issues in their own collapsed group with an undo button", async () => {
		const calls = open("owner", [issue(), known]);
		const summary = await screen.findByText("پذیرفته‌شده (۱)");
		const group = summary.closest("details") as HTMLDetailsElement;
		expect(group.open).toBe(false);
		await userEvent.click(summary);
		const table = within(group).getByRole("region", { name: "جدول مشکل‌های پذیرفته‌شده" });
		expect(within(table).getByText("عماد")).toBeTruthy();
		expect(within(table).getByText("دیسک جدید در راه است")).toBeTruthy();
		expect(within(table).getByText("همیشه")).toBeTruthy();
		// the main table keeps only the open issue
		const main = screen.getByRole("grid", { name: "فهرست مشکلات" });
		expect(within(main).queryByText("nl-2")).toBeNull();
		await userEvent.click(within(table).getByRole("button", { name: "لغو پذیرش" }));
		await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
		const del = calls.find((c) => c.method === "DELETE");
		expect(del?.path).toBe("/issues/ack");
		expect(new URLSearchParams(del?.search).get("key")).toBe("server:2:disk");
	});

	it("shows no acknowledge or undo button to a viewer", async () => {
		open("viewer", [issue(), known]);
		await screen.findByText("پذیرفته‌شده (۱)");
		expect(screen.queryByRole("button", { name: /^پذیرفتن/ })).toBeNull();
		expect(screen.queryByRole("button", { name: "لغو پذیرش" })).toBeNull();
	});
});
