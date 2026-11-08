import { toast } from "@nyxon/nasim";
import { t } from "@/strings";

const UPDATE_CHECK_MS = 60 * 60 * 1000;

// A new worker takes over at once (skipWaiting); the page asks for a reload instead of forcing one.
function watchForUpdates(registration: ServiceWorkerRegistration, hadController: boolean) {
	let prompted = false;
	navigator.serviceWorker.addEventListener("controllerchange", () => {
		if (!hadController || prompted) return;
		prompted = true;
		toast(t.pwa.updateTitle, {
			timeout: 0,
			actionProps: { children: t.pwa.updateReload, onPress: () => location.reload() },
		});
	});
	let checked = Date.now();
	document.addEventListener("visibilitychange", () => {
		if (document.visibilityState !== "visible" || Date.now() - checked < UPDATE_CHECK_MS) return;
		checked = Date.now();
		void registration.update().catch(() => {});
	});
}

// A failure costs nothing: the panel works without the worker.
const register = () => {
	const hadController = navigator.serviceWorker.controller !== null;
	navigator.serviceWorker
		.register("/sw.js", { scope: "/", updateViaCache: "none" })
		.then((registration) => watchForUpdates(registration, hadController))
		.catch(() => {});
};

/** Registers /sw.js after the page has loaded; production only, so dev is never cached. */
export function registerWorker(): void {
	if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
	if (document.readyState === "complete") register();
	else addEventListener("load", register, { once: true });
}
