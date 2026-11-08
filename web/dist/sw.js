const CACHE = "downtimeless-6e11f672f4";
const FILES = ["/assets/CollectionBuilder-D52yCX8D.js","/assets/CopyButton-BE6PwspP.js","/assets/DataTable-C6gCkUYp.js","/assets/Loadable-obc6NK8v.js","/assets/Modal-aqiGpEjM.js","/assets/StaticTable-BRKxUpCK.js","/assets/Tabs-DH1Dl7T0.js","/assets/_app-CkmM2xCI.js","/assets/_app-DfVJ7OIQ.js","/assets/accent-9pZLV5-s.js","/assets/account-BwIIkiL_.js","/assets/api-keys-D5TkGcoh.js","/assets/auth-DB9WN9CF.js","/assets/color-MwUzspQ2.js","/assets/index-B3MA8c6s.js","/assets/index-Dt9SeM_B.css","/assets/issues-CF04k4x_.js","/assets/lazyRouteComponent-Ckl1fAVF.js","/assets/link-DCSP6Z7R.js","/assets/login-CNSYoxh2.js","/assets/ping-matrix-BJBhbQZZ.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-ByDUbUNJ.js","/assets/servers._serverId-CShR2UQh.js","/assets/servers.index-BM_G_LU3.js","/assets/settings-K-LM2En2.js","/assets/ssl-BfIOya0t.js","/assets/ssl-DHZzxaRg.js","/assets/tooltip-DmguuJlF.js","/assets/useMatch-BDs0_k8J.js","/assets/useRefreshAll-BU30j6We.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
