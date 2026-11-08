const CACHE = "downtimeless-68d178027d";
const FILES = ["/assets/CollectionBuilder-D7RdoTbu.js","/assets/CopyButton-B-3mJ9rH.js","/assets/DataTable-7t_V63gt.js","/assets/Loadable-CW2i-DrH.js","/assets/Modal-CR1w1Fgj.js","/assets/StaticTable-BGdfOBMq.js","/assets/Tabs-KfbqHrzt.js","/assets/_app-CDCwttwS.js","/assets/_app-m3Oydg56.js","/assets/accent-9pZLV5-s.js","/assets/account-CTiE14wL.js","/assets/api-keys-BU3iDNYw.js","/assets/auth-D7TuThsF.js","/assets/color-MwUzspQ2.js","/assets/index--icn2Lrl.css","/assets/index-eFLAWZGX.js","/assets/issues-CTs3hoL2.js","/assets/lazyRouteComponent-CrRb4Iw6.js","/assets/link-DKYgEPsN.js","/assets/login-Du9BTaxu.js","/assets/ping-matrix-CMK9EGiw.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-DBYpi3Ks.js","/assets/servers._serverId-CVzS8PuY.js","/assets/servers.index-BMLoKYaa.js","/assets/settings-BPqh8c4t.js","/assets/ssl-CQXF39Am.js","/assets/ssl-CkyDbw1D.js","/assets/tooltip-DDJUlioP.js","/assets/useMatch-WM4cCCUp.js","/assets/useRefreshAll-8BuWPOLj.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
