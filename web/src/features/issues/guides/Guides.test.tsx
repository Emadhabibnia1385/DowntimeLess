import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { GuideFa, Issue, PlaybookItem } from "@/api/generated/model";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

const me = {
	id: 1,
	name: "T",
	username: null,
	role: "viewer",
	has_password: false,
	workspace: { id: 1, name: "فضای کار اصلی", role: "viewer", is_personal: true },
	tg_username: null,
};

const issue: Issue = {
	id: "server:1:disk",
	server_id: 1,
	server_name: "de-1",
	code: "disk",
	severity: "warning",
	title: "دیسک رو به پر شدن است",
	suggestion: "لاگ‌ها را پاک کنید",
	evidence: { disk_pct: 91 },
	recent_24h: 1,
	acked: false,
};

const item = (code: string, theme: string, title_fa: string | null): PlaybookItem => ({
	code,
	theme,
	title: code,
	summary_fa: "",
	detector: "live",
	title_fa,
	meaning_fa: title_fa ? `معنی ${title_fa}` : null,
});

const guide: GuideFa = {
	code: "disk",
	title: "دیسک رو به پر شدن است",
	meaning: "درصد استفادهٔ دیسک از حد هشدار گذشته است.",
	why: "دیسک پر سرویس‌ها را می‌خواباند.",
	checks: [
		{ text: "فضای آزاد را ببینید.", cmd: "df -h /" },
		{ text: "در پنل سرویس‌دهنده نگاه کنید.", cmd: null },
	],
	fixes: [{ text: "لاگ را کوچک کنید.", cmd: "journalctl --vacuum-size=200M" }],
	fixed_when: ["درصد دیسک زیر حد هشدار برگردد."],
	never: ["تازه‌ترین dump را پاک نکنید."],
};

function open(path: string) {
	const calls: string[] = [];
	const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
		const url = new URL(String(input), "http://localhost");
		const route = url.pathname.replace(/^.*\/api\/v1/, "");
		calls.push(route + url.search);
		const body: unknown =
			route === "/auth/me"
				? me
				: route === "/issues"
					? [issue]
					: route === "/reports/playbooks"
						? {
								principles: [],
								playbooks: [
									item("disk", "host", "دیسک رو به پر شدن است"),
									item("node_down", "node", "نود در پنل وصل نیست"),
									item("quota_exhausted", "quota", null),
								],
							}
						: route.startsWith("/reports/playbooks/")
							? { matched: true, playbook: {}, guide_fa: guide }
							: [];
		return new Response(JSON.stringify(body), {
			status: 200,
			headers: { "Content-Type": "application/json" },
		});
	});
	vi.stubGlobal("fetch", fetchMock);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: [path] }),
	});
	const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
	render(<AppProviders queryClient={queryClient} router={router} />);
	return calls;
}

describe("fix guides", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("opens the Persian guide of an issue row for a viewer, commands to copy and no run button", async () => {
		const calls = open("/issues");
		await userEvent.click(
			await screen.findByRole("button", { name: "راهنمای رفع «دیسک رو به پر شدن»" }),
		);
		const dialog = await screen.findByRole("dialog");
		expect(await within(dialog).findByText("df -h /")).toBeTruthy();
		expect(within(dialog).getByText("journalctl --vacuum-size=200M")).toBeTruthy();
		expect(within(dialog).getByText("از کجا بفهمیم رفع شد")).toBeTruthy();
		expect(within(dialog).getAllByRole("button", { name: "کپی" })).toHaveLength(2);
		expect(within(dialog).queryByRole("button", { name: /اجرا/ })).toBeNull();
		expect(calls).toContain("/reports/playbooks/disk?lang=fa");
	});

	it("lists the guides in their own tab, searchable by code or title", async () => {
		open("/issues?tab=guides");
		expect(await screen.findByText("نود در پنل وصل نیست")).toBeTruthy();
		expect(screen.queryByText("quota_exhausted")).toBeNull();
		await userEvent.type(screen.getByRole("searchbox", { name: "جستجوی راهنما" }), "node");
		await waitFor(() => expect(screen.queryByText("دیسک رو به پر شدن است")).toBeNull());
		await userEvent.click(
			screen.getByRole("button", { name: "باز کردن راهنمای «نود در پنل وصل نیست»" }),
		);
		expect(await within(await screen.findByRole("dialog")).findByText("df -h /")).toBeTruthy();
	});
});
