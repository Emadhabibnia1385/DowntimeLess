import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory, createRouter } from "@tanstack/react-router";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppProviders } from "@/app/providers";
import { routeTree } from "@/routeTree.gen";
import { DEFAULT_SETTINGS, onKey, RULES } from "../lib/rules";

const owner = {
	id: 1,
	name: "T",
	username: null,
	role: "owner",
	has_password: false,
	workspace: { id: 1, name: "فضای کار اصلی", role: "owner", is_personal: true },
	tg_username: null,
};
const CHANNELS = [
	{ id: 1, name: "کانال هشدار", chat_id: "-1001234567890", created_at: 1 },
	{ id: 2, name: "گروه فنی", chat_id: "@tech_alerts", created_at: 2 },
];

type Call = { method: string; url: string; body: unknown };

function stub(role = "owner", channels = CHANNELS) {
	const calls: Call[] = [];
	const routes: Record<string, string> = Object.fromEntries(
		RULES.map((rule) => [rule.id, rule.id === "offline" ? "admins" : "panel"]),
	);
	vi.stubGlobal(
		"fetch",
		vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
			const url = String(input);
			const method = init?.method ?? "GET";
			const body = init?.body ? JSON.parse(String(init.body)) : undefined;
			calls.push({ method, url, body });
			const json = (data: unknown, status = 200) =>
				new Response(status === 204 ? null : JSON.stringify(data), {
					status,
					headers: { "Content-Type": "application/json" },
				});
			if (url.endsWith("/auth/me")) return json({ ...owner, role });
			if (url.endsWith("/settings")) return json(DEFAULT_SETTINGS);
			if (url.endsWith("/telegram/routes")) return json(routes);
			if (url.endsWith("/telegram/channels") && method === "GET") return json(channels);
			if (url.endsWith("/telegram/channels") && method === "POST") {
				return json({ id: 3, created_at: 3, ...body }, 201);
			}
			if (url.includes("/telegram/channels/")) return json(null, 204);
			return json([]);
		}),
	);
	return calls;
}

async function open(role = "owner", channels = CHANNELS) {
	const calls = stub(role, channels);
	const router = createRouter({
		routeTree,
		history: createMemoryHistory({ initialEntries: ["/account?tab=notifications"] }),
	});
	const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
	render(<AppProviders queryClient={queryClient} router={router} />);
	await screen.findByRole("grid", { name: "فهرست اعلان‌ها" }).catch(() => null);
	return calls;
}

const table = () => screen.getByRole("region", { name: "فهرست اعلان‌ها" });
const line = (title: string) =>
	within(table())
		.getAllByRole("row")
		.find((row) => within(row).queryByText(title)) as HTMLElement;

describe("NotificationsTab destinations", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("gives every alert a destination select that shows where it goes now", async () => {
		await open();
		await screen.findByRole("region", { name: "فهرست اعلان‌ها" });
		expect(within(table()).getAllByRole("button", { name: /مقصد اعلان/ })).toHaveLength(
			RULES.length,
		);
		const offline = within(line("قطع شدن سرور")).getByRole("button", {
			name: /مقصد اعلان قطع شدن سرور/,
		});
		expect(offline.textContent).toContain("مدیران (پیام خصوصی)");
		const cpu = within(line("مصرف پردازنده")).getByRole("button", {
			name: /مقصد اعلان مصرف پردازنده/,
		});
		expect(cpu.textContent).toContain("فقط پنل");
	});

	it("offers the panel, the admins and each channel by name", async () => {
		await open();
		await screen.findByRole("region", { name: "فهرست اعلان‌ها" });
		await userEvent.click(
			within(line("مصرف پردازنده")).getByRole("button", { name: /مقصد اعلان/ }),
		);
		const options = (await screen.findAllByRole("option")).map((option) => option.textContent);
		expect(options).toEqual(["فقط پنل", "مدیران (پیام خصوصی)", "کانال هشدار", "گروه فنی"]);
	});

	it("saves the chosen destination with the same button as the levels", async () => {
		const calls = await open();
		await screen.findByRole("region", { name: "فهرست اعلان‌ها" });
		await userEvent.click(
			within(line("مصرف پردازنده")).getByRole("button", { name: /مقصد اعلان/ }),
		);
		await userEvent.click(await screen.findByRole("option", { name: "گروه فنی" }));
		await userEvent.click(screen.getByRole("button", { name: "ذخیرهٔ اعلان‌ها" }));
		await waitFor(() =>
			expect(calls.some((c) => c.method === "PUT" && c.url.endsWith("/telegram/routes"))).toBe(
				true,
			),
		);
		const put = calls.find((c) => c.method === "PUT" && c.url.endsWith("/telegram/routes"));
		expect(put?.body).toMatchObject({ cpu: "channel:2", offline: "admins" });
		const settings = calls.find((c) => c.method === "PUT" && c.url.endsWith("/settings"));
		expect(settings?.body).toMatchObject({ [onKey("cpu")]: 1, cpu_warn: 90 });
		expect(Object.keys(settings?.body as object).some((key) => key.startsWith("route_"))).toBe(
			false,
		);
	});

	it("has a switch for each of the new detectors", async () => {
		await open();
		await screen.findByRole("region", { name: "فهرست اعلان‌ها" });
		for (const title of [
			"ریبوت شدن سرور",
			"تغییر آی‌پی عمومی",
			"مسدود شدن آی‌پی در ایران",
			"پیش‌بینی حجم ماهانه",
			"بار سیستم به‌ازای هسته",
		]) {
			expect(within(line(title)).getByRole("switch")).toBeTruthy();
		}
	});
});

describe("NotificationsTab phase 2 and 3 rows", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("groups the rows under headings, the host checks and panel rules included", async () => {
		await open();
		await screen.findByRole("region", { name: "فهرست اعلان‌ها" });
		for (const heading of [
			"لیسنرها، تانل‌ها و کانتینرها",
			"DNAT، conntrack و کرنل",
			"پنل PasarGuard",
		]) {
			expect(within(table()).getByText(heading)).toBeTruthy();
		}
		for (const title of [
			"بسته شدن پورت همیشگی",
			"توقف سرویس تانل یا DNAT",
			"توقف کانتینر",
			"از بین رفتن DNAT",
			"دور ریختن اتصال در conntrack",
			"نود «وصل» با Xray متوقف",
			"افت ناگهانی مصرف نود",
			"حجم نماینده‌ها",
			"اینباند بدون گروه",
		]) {
			expect(within(line(title)).getByRole("switch")).toBeTruthy();
		}
		const rows = within(table()).getAllByRole("row");
		expect(rows).toHaveLength(RULES.length + 5 + 1); // the rules, five group headings, the header row
	});

	it("tunes the numbers of the new rules and names the two conntrack limits", async () => {
		const calls = await open();
		await screen.findByRole("region", { name: "فهرست اعلان‌ها" });
		const conntrack = line("برگشت حد conntrack به پیش‌فرض");
		expect(within(conntrack).getByText("کمینهٔ رله")).toBeTruthy();
		expect(within(conntrack).getByText("کمینهٔ نود")).toBeTruthy();
		const reseller = within(line("حجم نماینده‌ها")).getByRole("textbox", { name: /مقدار هشدار/ });
		await userEvent.clear(reseller);
		await userEvent.type(reseller, "80");
		await userEvent.click(screen.getByRole("button", { name: "ذخیرهٔ اعلان‌ها" }));
		await waitFor(() =>
			expect(calls.some((c) => c.method === "PUT" && c.url.endsWith("/settings"))).toBe(true),
		);
		const put = calls.find((c) => c.method === "PUT" && c.url.endsWith("/settings"));
		expect(put?.body).toMatchObject({
			reseller_warn: 80,
			reseller_crit: 95,
			ct_max_relay: 65536,
			ct_max_exit: 262144,
			node_drop_pct: 30,
			node_others_pct: 70,
			[onKey("node_silent")]: 1,
		});
	});

	it("keeps a reseller critical level from going below its warning level", async () => {
		const calls = await open();
		await screen.findByRole("region", { name: "فهرست اعلان‌ها" });
		const crit = within(line("حجم نماینده‌ها")).getByRole("textbox", { name: /مقدار بحرانی/ });
		await userEvent.clear(crit);
		await userEvent.type(crit, "50");
		await userEvent.click(screen.getByRole("button", { name: "ذخیرهٔ اعلان‌ها" }));
		expect(
			await screen.findByText("مقدار بحرانی باید از مقدار هشدار بیشتر یا برابر آن باشد."),
		).toBeTruthy();
		expect(calls.some((c) => c.method === "PUT" && c.url.endsWith("/settings"))).toBe(false);
	});
});

describe("ChannelsCard", () => {
	beforeEach(() => {
		window.scrollTo = () => {};
	});
	afterEach(() => vi.unstubAllGlobals());

	it("lists the channels in a table with a test and a delete button each", async () => {
		await open();
		const card = await screen.findByRole("region", { name: "فهرست کانال‌های تلگرام" });
		const rows = within(card).getAllByRole("row");
		expect(rows).toHaveLength(3);
		expect(within(rows[1]).getByText("کانال هشدار")).toBeTruthy();
		expect(within(rows[1]).getByText("-1001234567890")).toBeTruthy();
		expect(within(rows[2]).getByText("@tech_alerts")).toBeTruthy();
		expect(
			within(rows[1]).getByRole("button", { name: "ارسال پیام آزمایشی به کانال هشدار" }),
		).toBeTruthy();
		expect(within(rows[1]).getByRole("button", { name: "حذف کانال کانال هشدار" })).toBeTruthy();
		expect(screen.getByRole("heading", { name: "کانال‌های تلگرام" })).toBeTruthy();
		expect(screen.getByText(/ربات باید در کانال یا گروه مدیر باشد/)).toBeTruthy();
	});

	it("sends a test message through the master", async () => {
		const calls = await open();
		const card = await screen.findByRole("region", { name: "فهرست کانال‌های تلگرام" });
		await userEvent.click(
			within(card).getByRole("button", { name: "ارسال پیام آزمایشی به گروه فنی" }),
		);
		await waitFor(() =>
			expect(
				calls.some((c) => c.method === "POST" && c.url.endsWith("/telegram/channels/2/test")),
			).toBe(true),
		);
	});

	it("deletes a channel only after a confirmation", async () => {
		const calls = await open();
		const card = await screen.findByRole("region", { name: "فهرست کانال‌های تلگرام" });
		await userEvent.click(within(card).getByRole("button", { name: "حذف کانال کانال هشدار" }));
		expect(calls.some((c) => c.method === "DELETE")).toBe(false);
		// several alerts can be mounted at once, so pick the dialog by its title
		const dialog = (await screen.findByText("حذف این کانال؟")).closest(
			"[role=alertdialog]",
		) as HTMLElement;
		await userEvent.click(within(dialog).getByRole("button", { name: "حذف" }));
		await waitFor(() =>
			expect(
				calls.some((c) => c.method === "DELETE" && c.url.endsWith("/telegram/channels/1")),
			).toBe(true),
		);
	});

	it("adds a channel from a dialog and refuses a bad chat id before asking the master", async () => {
		const calls = await open();
		await screen.findByRole("region", { name: "فهرست کانال‌های تلگرام" });
		await userEvent.click(screen.getByRole("button", { name: "افزودن کانال" }));
		const dialog = await screen.findByRole("dialog");
		await userEvent.type(within(dialog).getByRole("textbox", { name: /نام کانال/ }), "اضطراری");
		await userEvent.type(within(dialog).getByRole("textbox", { name: /شناسهٔ چت/ }), "not a chat");
		await userEvent.click(within(dialog).getByRole("button", { name: "افزودن" }));
		expect(
			await within(dialog).findByText("شناسه باید عددی (مثل -100…) یا نام کاربری با @ باشد."),
		).toBeTruthy();
		expect(calls.some((c) => c.method === "POST")).toBe(false);
		const chat = within(dialog).getByRole("textbox", { name: /شناسهٔ چت/ });
		await userEvent.clear(chat);
		await userEvent.type(chat, "-1009876543210");
		await userEvent.click(within(dialog).getByRole("button", { name: "افزودن" }));
		await waitFor(() =>
			expect(calls.some((c) => c.method === "POST" && c.url.endsWith("/telegram/channels"))).toBe(
				true,
			),
		);
		const post = calls.find((c) => c.method === "POST" && c.url.endsWith("/telegram/channels"));
		expect(post?.body).toEqual({ name: "اضطراری", chat_id: "-1009876543210" });
	});

	it("shows an empty state when there are no channels", async () => {
		await open("owner", []);
		expect(await screen.findByText("هنوز کانالی اضافه نشده")).toBeTruthy();
	});

	it("hides destinations and channels from a viewer, who cannot call the telegram API", async () => {
		const calls = await open("viewer");
		await screen.findByRole("region", { name: "فهرست اعلان‌ها" });
		expect(screen.queryByRole("heading", { name: "کانال‌های تلگرام" })).toBeNull();
		expect(within(table()).queryAllByRole("button", { name: /مقصد اعلان/ })).toHaveLength(0);
		expect(calls.some((c) => c.url.includes("/telegram/"))).toBe(false);
	});
});
