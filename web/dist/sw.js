const CACHE = "downtimeless-032ea703ae";
const FILES = ["/assets/CollectionBuilder-D2RZOSgQ.js","/assets/CopyButton-CbGsPhaZ.js","/assets/DataTable-7dbsI4CG.js","/assets/Loadable-C4d8t1Sz.js","/assets/Modal-DffWGGnC.js","/assets/StaticTable-D2ufPrxw.js","/assets/Tabs-DCWNgB0F.js","/assets/_app-CcN166z_.js","/assets/_app-DlLk9Oc4.js","/assets/accent-9pZLV5-s.js","/assets/account-47wzrE8d.js","/assets/api-keys-OxfoiXR7.js","/assets/auth-D1kvaBUs.js","/assets/color-MwUzspQ2.js","/assets/index-BRGMKhAu.js","/assets/index-DwVZvt2e.css","/assets/issues-Baa9bBzp.js","/assets/issues-_4nhg1xd.js","/assets/lazyRouteComponent-BYpk1QhB.js","/assets/link-fpzD6g30.js","/assets/login-C-grCkJV.js","/assets/ping-matrix-BOfHPMyr.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BrBdIVLO.js","/assets/servers._serverId-DRzIe9qf.js","/assets/servers.index-wwkM8Yf-.js","/assets/settings-C3xhrkv2.js","/assets/ssl-CT8LfTkC.js","/assets/ssl-Ca6BQJD-.js","/assets/tooltip-CBYMUqz_.js","/assets/useMatch-CspyuH5l.js","/assets/useRefreshAll-CUVd4PWQ.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
