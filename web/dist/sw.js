const CACHE = "downtimeless-9da05440b5";
const FILES = ["/assets/CopyButton-Du69QNg1.js","/assets/DataTable-NUVi9O1h.js","/assets/Loadable-DXRu_DTG.js","/assets/Modal-DOcpiVwU.js","/assets/StaticTable-jb0Wz7rE.js","/assets/Tabs-VRn0kJo8.js","/assets/_app-Bt6oj-6G.js","/assets/_app-DfWlQb4V.js","/assets/accent-9pZLV5-s.js","/assets/account-C3Hm1mGl.js","/assets/api-keys-BzZG6cY6.js","/assets/auth-Msj5ljJD.js","/assets/color-MwUzspQ2.js","/assets/index-BGD8GWRn.css","/assets/index-LkrBNj0l.js","/assets/issues-APY7jLv0.js","/assets/issues-BGFfjIcb.js","/assets/lazyRouteComponent-Db6okk1V.js","/assets/link-DAKmGeVA.js","/assets/login-CEvMlBjP.js","/assets/ping-matrix-DvaRG1Uj.js","/assets/reports-CNQ6xD14.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-CTM3o_lP.js","/assets/servers._serverId-Cnq9eTyr.js","/assets/servers.index-DJ1fWJ9A.js","/assets/settings-CTr8B-lv.js","/assets/ssl-DS3E3f9y.js","/assets/ssl-HBzMXSI0.js","/assets/tooltip-cQGui-k2.js","/assets/traffic-BKgdj0YC.js","/assets/traffic-eWcZ29KA.js","/assets/useMatch-Cqguhu1N.js","/assets/useRefreshAll-2lQ-EG_D.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
