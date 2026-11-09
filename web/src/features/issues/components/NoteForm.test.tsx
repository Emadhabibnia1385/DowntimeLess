import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

const me = (role: string) => ({
	id: 1,
	name: "T",
	username: null,
	role,
	has_password: false,
	workspace: { id: 1, name: "فضای کار اصلی", role, is_personal: true },
	tg_username: null,
});

function open(role: string) {
	const posted: unknown[] = [];
	const note = {
		id: 9,
		ts: 1_700_000_000,
		server_id: null,
		server: null,
		kind: "note",
		title: "Arno DNAT changed",
		detail: { text: "Arno DNAT changed" },
	};
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
			const url = new URL(String(input), "http://localhost");
			const route = url.pathname.replace(/^.*\/api\/v1/, "");
			if (route === "/changes" && init?.method === "POST") {
				posted.push(JSON.parse(String(init.body)));
				return new Response(JSON.stringify(note), { status: 201 });
			}
			const body: unknown =
				route === "/auth/me"
					? me(role)
					: route === "/reports/changes"
						? { since: 0, until: 1, events: posted.length ? [note] : [], truncated: false }
						: route === "/servers"
							? [{ id: 3, name: "arno", alias: "", country: "IR" }]
							: [];
			return new Response(JSON.stringify(body), {
				status: 200,
				headers: { "Content-Type": "application/json" },
			});
		}),
	);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: ["/issues?tab=changes"] }),
	});
	const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
	render(<AppProviders queryClient={queryClient} router={router} />);
	return posted;
}

describe("change notes", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("lets an admin write a note that then shows in the change log", async () => {
		const posted = open("admin");
		await userEvent.type(
			await screen.findByRole("textbox", { name: /یادداشت/ }),
			"Arno DNAT changed",
		);
		await userEvent.click(screen.getByRole("button", { name: "ثبت یادداشت" }));
		await waitFor(() => expect(posted).toEqual([{ text: "Arno DNAT changed", server_id: null }]));
		expect(await screen.findByText("Arno DNAT changed")).toBeTruthy();
	});

	it("refuses an empty note in the form", async () => {
		const posted = open("owner");
		await userEvent.click(await screen.findByRole("button", { name: "ثبت یادداشت" }));
		expect(await screen.findByText("متن یادداشت را بنویسید.")).toBeTruthy();
		expect(posted).toEqual([]);
	});

	it("hides the form from viewers and operators", async () => {
		open("operator");
		expect(await screen.findByRole("tab", { name: "تغییرات" })).toBeTruthy();
		await waitFor(() => expect(screen.queryByRole("button", { name: "ثبت یادداشت" })).toBeNull());
		expect(screen.queryByRole("textbox", { name: /یادداشت/ })).toBeNull();
	});
});
