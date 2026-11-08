import { afterEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "./transport";
import { setTabWorkspace, tabWorkspace } from "./workspace";

const ok = () => new Response("{}", { headers: { "Content-Type": "application/json" } });

describe("the tab's workspace", () => {
	afterEach(() => {
		setTabWorkspace(null);
		vi.unstubAllGlobals();
	});

	it("is named on every request once known, and kept per tab in sessionStorage", async () => {
		const fetch = vi.fn(async (_url: string, _init?: RequestInit) => ok());
		vi.stubGlobal("fetch", fetch);
		await apiFetch("/api/v1/servers");
		expect(new Headers(fetch.mock.calls[0]?.[1]?.headers).get("X-Workspace-Id")).toBeNull();
		setTabWorkspace(7);
		await apiFetch("/api/v1/settings", { method: "PUT", body: "{}" });
		expect(new Headers(fetch.mock.calls[1]?.[1]?.headers).get("X-Workspace-Id")).toBe("7");
		expect(sessionStorage.getItem("dl.workspace")).toBe("7");
		expect(tabWorkspace()).toBe(7);
	});

	it("forgets a value that is not a workspace id", () => {
		setTabWorkspace(null);
		expect(sessionStorage.getItem("dl.workspace")).toBeNull();
		expect(tabWorkspace()).toBeNull();
	});
});
