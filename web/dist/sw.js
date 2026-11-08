const CACHE = "downtimeless-9e2cedb1c4";
const FILES = ["/assets/CopyButton-CRHgEMhO.js","/assets/DataTable-CtzzgdCc.js","/assets/Loadable-BrE2zYCB.js","/assets/Modal-5y6g8Kr9.js","/assets/StaticTable-DcOwfsRy.js","/assets/Tabs-DIkoMHO_.js","/assets/_app-COAHZTHq.js","/assets/_app-D9hL7llz.js","/assets/accent-9pZLV5-s.js","/assets/account-Cq4nHmSR.js","/assets/api-keys-D9FnjQ68.js","/assets/auth-C_tX1kJO.js","/assets/color-MwUzspQ2.js","/assets/index-DnphI-5j.css","/assets/index-DxMHTdyk.js","/assets/issues-B-0dJz9e.js","/assets/issues-CEmtJHL7.js","/assets/lazyRouteComponent-Bjht9mME.js","/assets/link-BRReOtVq.js","/assets/login-pRF2caAZ.js","/assets/ping-matrix-Dzlp22eX.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BsQAhV5D.js","/assets/servers._serverId-CcyGn90G.js","/assets/servers.index-Ac888iC4.js","/assets/settings-DOb0-NMY.js","/assets/ssl-DIfW3yZM.js","/assets/ssl-Drg8FCSz.js","/assets/tooltip-DI7vq01a.js","/assets/traffic-Bjbv7ui4.js","/assets/useMatch-ZpPr0AJl.js","/assets/useRefreshAll-DcjPyxOq.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
const NEVER = ["/api/","/agent/","/llms.txt"];
const OFFLINE = "/offline.html";
self.addEventListener("install", (event) => {
	event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (event) => {
	const old = (keys) => keys.filter((key) => key.startsWith("downtimeless-") && key !== CACHE);
	event.waitUntil(
		caches.keys()
			.then((keys) => Promise.all(old(keys).map((key) => caches.delete(key))))
			.then(() => self.clients.claim()),
	);
});
self.addEventListener("fetch", (event) => {
	const { request } = event;
	const { origin, pathname } = new URL(request.url);
	if (request.method !== "GET" || origin !== location.origin) return;
	if (NEVER.some((prefix) => pathname.startsWith(prefix))) return;
	if (request.mode === "navigate") {
		event.respondWith(
			fetch(request).catch(() => caches.open(CACHE).then((cache) => cache.match(OFFLINE))),
		);
		return;
	}
	if (!FILES.includes(pathname)) return;
	event.respondWith(
		caches.open(CACHE).then((cache) => cache.match(request)).then((hit) => hit || fetch(request)),
	);
});
