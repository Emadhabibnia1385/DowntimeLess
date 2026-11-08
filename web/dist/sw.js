const CACHE = "downtimeless-bb21d70888";
const FILES = ["/assets/CollectionBuilder-W7c7B4dz.js","/assets/ConfirmDialog-WRADJ0gC.js","/assets/CopyButton-Dek0-QmP.js","/assets/DataTable-Le73ezcB.js","/assets/KeyValueList-C4jtbc8F.js","/assets/Loadable-CwYll6ZG.js","/assets/Modal-CS5KrRXA.js","/assets/StatusChip-B6vO2-Ne.js","/assets/_app-C5jLX0n5.js","/assets/_app-_n-8DGaO.js","/assets/accent-9pZLV5-s.js","/assets/account-7XC8rePX.js","/assets/api-keys-llxJ_7Q8.js","/assets/auth-C1_t9s8Z.js","/assets/color-MwUzspQ2.js","/assets/index-4HnARnDt.js","/assets/index-DrIyD-wQ.css","/assets/issues-CUsa-Xkc.js","/assets/issues-I4AwjyoS.js","/assets/lazyRouteComponent-BIeWYpnW.js","/assets/link-Dw3TXCvh.js","/assets/login-CBMothCK.js","/assets/number-CofhuNGI.js","/assets/overview-PkC57jqm.js","/assets/ping-matrix-C6mjIQDT.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-0EWmFcXB.js","/assets/servers-Dns4nMKI.js","/assets/servers._serverId-CBXDdNdR.js","/assets/servers.index-Dt5Gj9YR.js","/assets/ssl-CgGA-Ic5.js","/assets/ssl-D1O9CvQE.js","/assets/tooltip-DI6B3TfW.js","/assets/useDocumentTitle-VA7kgxF4.js","/assets/useListState-Byx61Dth.js","/assets/useLoadMoreSentinel-Bzs5Oehd.js","/assets/useMatch-Vx09SLZy.js","/assets/useRefreshAll-nJyeGvW0.js","/assets/useSlot-xB10OGmG.js","/assets/useToggleState-DRLvtfPj.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
