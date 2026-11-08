import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resolveInstallState } from "./installPrompt";

// The store is module state and listens on window, so each case loads it afresh and unhooks it.
const hooked: [string, EventListener][] = [];

beforeEach(() => {
	const add = window.addEventListener.bind(window);
	vi.spyOn(window, "addEventListener").mockImplementation(
		(type: string, listener: EventListenerOrEventListenerObject) => {
			hooked.push([type, listener as EventListener]);
			add(type, listener);
		},
	);
});

afterEach(() => {
	for (const [type, listener] of hooked.splice(0)) window.removeEventListener(type, listener);
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
});

async function load() {
	vi.resetModules();
	const module = await import("./installPrompt");
	module.watchInstallPrompt();
	return module;
}

function offer(outcome: "accepted" | "dismissed") {
	const prompt = vi.fn(async () => {});
	const event = Object.assign(new Event("beforeinstallprompt", { cancelable: true }), {
		prompt,
		userChoice: Promise.resolve({ outcome }),
	});
	act(() => void window.dispatchEvent(event));
	return { event, prompt };
}

function standalone(on: boolean) {
	vi.stubGlobal("matchMedia", (query: string) => ({
		matches: on && query === "(display-mode: standalone)",
		media: query,
		addEventListener() {},
		removeEventListener() {},
	}));
}

describe("the install button's state", () => {
	const none = { standalone: false, installed: false, hasPrompt: false, ios: false };

	it("hides in an installed app or after the browser reports the install", () => {
		expect(resolveInstallState({ ...none, standalone: true, hasPrompt: true })).toBe("installed");
		expect(resolveInstallState({ ...none, installed: true, ios: true })).toBe("installed");
	});

	it("calls the prompt where the browser gave one, shows the steps on iOS, else hides", () => {
		expect(resolveInstallState({ ...none, hasPrompt: true })).toBe("prompt");
		expect(resolveInstallState({ ...none, ios: true })).toBe("ios");
		expect(resolveInstallState(none)).toBe("none");
	});
});

describe("the install prompt", () => {
	it("is kept when the browser sends it, and the browser's own bar is held back", async () => {
		const { useInstallState } = await load();
		const { result } = renderHook(() => useInstallState());
		expect(result.current).toBe("none");
		const { event } = offer("accepted");
		expect(event.defaultPrevented).toBe(true);
		expect(result.current).toBe("prompt");
	});

	it("is shown once on a press: the answer comes back and the button goes", async () => {
		const { promptInstall, useInstallState } = await load();
		const { result } = renderHook(() => useInstallState());
		const { prompt } = offer("dismissed");
		await expect(promptInstall()).resolves.toBe("dismissed");
		expect(prompt).toHaveBeenCalledOnce();
		expect(result.current).toBe("none");
		await expect(promptInstall()).resolves.toBe("unavailable");
	});

	it("is installed once the browser says so, and no prompt is left to call", async () => {
		const { promptInstall, useInstallState } = await load();
		const { result } = renderHook(() => useInstallState());
		offer("accepted");
		act(() => void window.dispatchEvent(new Event("appinstalled")));
		expect(result.current).toBe("installed");
		await expect(promptInstall()).resolves.toBe("unavailable");
	});

	it("stays hidden when the page already runs as an installed app", async () => {
		standalone(true);
		const { useInstallState } = await load();
		const { result } = renderHook(() => useInstallState());
		offer("accepted");
		expect(result.current).toBe("installed");
	});

	it("shows the iOS steps on an iPhone, which never sends a prompt", async () => {
		vi.stubGlobal("navigator", {
			...navigator,
			userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/605.1.15",
		});
		const { useInstallState } = await load();
		const { result } = renderHook(() => useInstallState());
		expect(result.current).toBe("ios");
	});
});
