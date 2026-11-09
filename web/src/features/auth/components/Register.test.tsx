import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";

type Call = { method: string; url: string; body: unknown };

function signedOut(open: boolean) {
	const calls: Call[] = [];
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
			const url = String(input);
			const method = init?.method ?? "GET";
			calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : null });
			if (url.endsWith("/auth/registration")) return Response.json({ open });
			if (url.endsWith("/auth/register"))
				return Response.json(
					{ code: "register.username_taken", message: "این نام کاربری گرفته شده است." },
					{ status: 409 },
				);
			return Response.json({ code: "auth.required", message: "x" }, { status: 401 });
		}),
	);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: ["/"] }),
	});
	render(
		<AppProviders
			queryClient={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
			router={router}
		/>,
	);
	return calls;
}

describe("sign-up on the login page", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("offers the form only while registration is open", async () => {
		signedOut(false);
		await screen.findByRole("button", { name: "ورود با تلگرام" });
		await waitFor(() =>
			expect(screen.queryByRole("button", { name: "ساخت حساب تازه" })).toBeNull(),
		);
	});

	it("checks both passwords before asking and shows the master's answer", async () => {
		const calls = signedOut(true);
		await userEvent.click(await screen.findByRole("button", { name: "ساخت حساب تازه" }));
		await userEvent.type(screen.getByRole("textbox", { name: /نام کاربری/ }), "Sara.K");
		const [pw, pw2] = screen.getAllByLabelText(/رمز عبور/);
		await userEvent.type(pw as HTMLElement, "long enough 1");
		await userEvent.type(pw2 as HTMLElement, "long enough 2");
		await userEvent.click(screen.getByRole("button", { name: "ساخت حساب و ورود" }));
		expect(await screen.findByText("تکرار رمز با رمز عبور یکی نیست.")).toBeTruthy();
		expect(calls.some((c) => c.url.endsWith("/auth/register"))).toBe(false);
		await userEvent.clear(pw2 as HTMLElement);
		await userEvent.type(pw2 as HTMLElement, "long enough 1");
		await userEvent.click(screen.getByRole("button", { name: "ساخت حساب و ورود" }));
		expect(await screen.findByText("این نام کاربری گرفته شده است.")).toBeTruthy();
		expect(calls.find((c) => c.url.endsWith("/auth/register"))?.body).toEqual({
			username: "sara.k",
			password: "long enough 1",
			password2: "long enough 1",
		});
		await userEvent.click(screen.getByRole("button", { name: "ورود" }));
		expect(await screen.findByRole("button", { name: "ورود با تلگرام" })).toBeTruthy();
	});
});
