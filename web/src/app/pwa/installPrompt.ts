import { useSyncExternalStore } from "react";

// Chrome and Edge hand over the install prompt once, early: it waits here for the button.
type InstallEvent = Event & {
	prompt: () => Promise<void>;
	userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

export type InstallState = "installed" | "prompt" | "ios" | "none";

let waiting: InstallEvent | null = null;
let installed = false;
const listeners = new Set<() => void>();
const notify = () => {
	for (const listener of listeners) listener();
};

const isStandalone = (): boolean =>
	matchMedia("(display-mode: standalone)").matches ||
	(navigator as Navigator & { standalone?: boolean }).standalone === true;

// Safari on iPhone and iPad has no prompt; iPadOS 13+ reports itself as a Mac with a touch screen.
export const isIosDevice = (): boolean =>
	/iphone|ipad|ipod/i.test(navigator.userAgent) ||
	(navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

/** What the install button does: nothing, call the browser's prompt, or show the iOS steps. */
export function resolveInstallState(facts: {
	standalone: boolean;
	installed: boolean;
	hasPrompt: boolean;
	ios: boolean;
}): InstallState {
	if (facts.standalone || facts.installed) return "installed";
	if (facts.hasPrompt) return "prompt";
	return facts.ios ? "ios" : "none";
}

/** Starts listening; call once at startup, the prompt can arrive before any screen is open. */
export function watchInstallPrompt(): void {
	addEventListener("beforeinstallprompt", (event) => {
		// The browser's own mini bar would pre-empt the page's button.
		event.preventDefault();
		waiting = event as InstallEvent;
		notify();
	});
	addEventListener("appinstalled", () => {
		waiting = null;
		installed = true;
		notify();
	});
	matchMedia("(display-mode: standalone)").addEventListener("change", notify);
}

/** Asks the browser to install the app; the prompt can be shown once, so it is spent either way. */
export async function promptInstall(): Promise<"accepted" | "dismissed" | "unavailable"> {
	const event = waiting;
	if (!event) return "unavailable";
	waiting = null;
	notify();
	await event.prompt();
	return (await event.userChoice).outcome;
}

const subscribe = (listener: () => void) => {
	listeners.add(listener);
	return () => void listeners.delete(listener);
};

const snapshot = (): InstallState =>
	resolveInstallState({
		standalone: isStandalone(),
		installed,
		hasPrompt: waiting !== null,
		ios: isIosDevice(),
	});

export const useInstallState = (): InstallState =>
	useSyncExternalStore(subscribe, snapshot, () => "none");
