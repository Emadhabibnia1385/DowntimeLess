const CACHE = "downtimeless-279ae3f8cb";
const FILES = ["/assets/CopyButton-DLuu6Rlp.js","/assets/DataTable-DpoIB3-a.js","/assets/Loadable-3aJy5-9V.js","/assets/Modal-BYTP542v.js","/assets/StaticTable-COYoVlBN.js","/assets/Tabs-Cb5FWayr.js","/assets/_app-BiSaic5r.js","/assets/_app-Bt21gyNn.js","/assets/accent-9pZLV5-s.js","/assets/account-z4ZFPip9.js","/assets/api-keys-BO8l-PW5.js","/assets/auth-B0jseRGA.js","/assets/color-MwUzspQ2.js","/assets/index-BstWcH8Y.js","/assets/index-D6KKesRd.css","/assets/issues-C9ACBnTU.js","/assets/issues-lK5zCbaz.js","/assets/lazyRouteComponent-B7xOCYO7.js","/assets/link-Ct9nkRTn.js","/assets/login-DPTmxFco.js","/assets/ping-matrix-Bv7iGj7o.js","/assets/reports-C9E6bZ1a.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-C8QDVCuZ.js","/assets/servers._serverId-6m7rv6Lo.js","/assets/servers.index-DwD_XNDe.js","/assets/settings-BBTgg9SE.js","/assets/ssl-C_z3YfjN.js","/assets/ssl-D3tUxPqi.js","/assets/tooltip-BraHW7Vl.js","/assets/traffic-DRNq5yYU.js","/assets/useMatch-Bijd88RT.js","/assets/useRefreshAll-NSJUy84D.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
