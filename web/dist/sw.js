const CACHE = "downtimeless-fb13ccca01";
const FILES = ["/assets/CollectionBuilder-BVWWMJ6X.js","/assets/CopyButton-DqIyNWI4.js","/assets/DataTable-B-WOtvDQ.js","/assets/Loadable-KZJT5AzA.js","/assets/Modal-Ge86zf76.js","/assets/StaticTable-NhXait4G.js","/assets/Tabs-DxlVCeqL.js","/assets/_app-CsunmN2X.js","/assets/_app-DQYcpp0m.js","/assets/accent-9pZLV5-s.js","/assets/account-jWPFFhp-.js","/assets/api-keys-CI7_bu1T.js","/assets/auth-DYnm7kxQ.js","/assets/color-MwUzspQ2.js","/assets/index-BUEkXD79.js","/assets/index-DME9JNRN.css","/assets/issues-BI2zBujE.js","/assets/issues-CIpGc1Yo.js","/assets/lazyRouteComponent-DbGHguzK.js","/assets/link-Bxz-rSBl.js","/assets/login-CKzslDDi.js","/assets/ping-matrix-sNcf7mga.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-CHKC859E.js","/assets/servers._serverId-tWOG54WH.js","/assets/servers.index-CSyIUye4.js","/assets/settings-DlNEk3MK.js","/assets/ssl-BxXHiGPv.js","/assets/ssl-DYK6E8Uw.js","/assets/tooltip-BuXHYCCo.js","/assets/traffic-C95MEQr0.js","/assets/useMatch-D09bPiq0.js","/assets/useRefreshAll-BL8sj8tx.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
