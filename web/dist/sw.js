const CACHE = "downtimeless-ce6c8c4183";
const FILES = ["/assets/ChoiceFields-B43nP8N5.js","/assets/CopyButton-DdSKEYh1.js","/assets/DataTable-OxkkXVdQ.js","/assets/Loadable-Bwh8q_oH.js","/assets/SelectField-BE61pkAI.js","/assets/StaticTable-Btz_81ew.js","/assets/StatusChip-B8Uf0ZHD.js","/assets/Tabs-Cxf9575C.js","/assets/_app-Bal9NUWu.js","/assets/_app-Dx0qxt4Q.js","/assets/accent-9pZLV5-s.js","/assets/account-C8XpHMGd.js","/assets/api-keys-CzYallrq.js","/assets/auth-9gfv7x-7.js","/assets/color-MwUzspQ2.js","/assets/index-DUKAd4dV.js","/assets/index-UkVgXYI8.css","/assets/issues-BKN1VRWO.js","/assets/issues-cNYM3GnB.js","/assets/lazyRouteComponent-DvcFmLSH.js","/assets/link-SC1oTJGx.js","/assets/login-CF68QeMW.js","/assets/members-DHwT1ey_.js","/assets/members-DwOFEo15.js","/assets/ping-matrix-MHnIdiYY.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-Ds-wb1q_.js","/assets/servers._serverId-Cyoj1IF9.js","/assets/servers.index-BxvpG2vs.js","/assets/settings-DMyYAL_Q.js","/assets/ssl-7DpBGMA5.js","/assets/ssl-B5hWq6NE.js","/assets/tooltip-CYs3v6bq.js","/assets/traffic-2Kxezak5.js","/assets/traffic-DyjRDB-_.js","/assets/useMatch-RkeCuxIl.js","/assets/useRefreshAll-4gFuLmMW.js","/assets/useSlot-DIEkaCDq.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
