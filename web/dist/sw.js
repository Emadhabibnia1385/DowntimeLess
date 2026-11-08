const CACHE = "downtimeless-e5b67273fe";
const FILES = ["/assets/CollectionBuilder-CK-slIU4.js","/assets/CopyButton-3HxYRPOf.js","/assets/DataTable-DN6kkbj6.js","/assets/Loadable-CkgvCX_k.js","/assets/Modal-BCKr72UV.js","/assets/StaticTable-D-hCiOI-.js","/assets/Tabs-DdIRKciB.js","/assets/_app-CUaqSaYQ.js","/assets/_app-XPFbENPK.js","/assets/accent-9pZLV5-s.js","/assets/account-Vul3m_Sl.js","/assets/api-keys-CB_9G9sc.js","/assets/auth-C-OibkI9.js","/assets/color-MwUzspQ2.js","/assets/index-CR5aCzOI.js","/assets/index-czmktykW.css","/assets/issues-CJGi-WhO.js","/assets/issues-tSKmrTxz.js","/assets/lazyRouteComponent-CpV979Tp.js","/assets/link-CLqAUKsH.js","/assets/login-d1z1gE9q.js","/assets/ping-matrix-B37aOhG6.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-ChsvhfDd.js","/assets/servers._serverId-CM0MG2zV.js","/assets/servers.index-CVUeXOOO.js","/assets/settings-Drk49w6N.js","/assets/ssl-BOQFoW08.js","/assets/ssl-o-ORmilm.js","/assets/tooltip-CwuiA3aK.js","/assets/traffic-CC3OP8RY.js","/assets/useMatch-I93vubUx.js","/assets/useRefreshAll-BTYsaccD.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
