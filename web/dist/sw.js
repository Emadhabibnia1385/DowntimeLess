const CACHE = "downtimeless-b72c91ea13";
const FILES = ["/assets/CopyButton-DLuu6Rlp.js","/assets/DataTable-DoJCRPgi.js","/assets/Loadable-3aJy5-9V.js","/assets/Modal-BYTP542v.js","/assets/StaticTable-COYoVlBN.js","/assets/Tabs-Cb5FWayr.js","/assets/_app-Dn-JNrvs.js","/assets/_app-_nP_naM7.js","/assets/accent-9pZLV5-s.js","/assets/account-B4AXGOl7.js","/assets/api-keys-I6OQgBz2.js","/assets/auth-B0jseRGA.js","/assets/color-MwUzspQ2.js","/assets/index-Bo48JU6Q.js","/assets/index-fHqbGeMc.css","/assets/issues-C8qaC_2r.js","/assets/issues-QSqlobXj.js","/assets/lazyRouteComponent-B7xOCYO7.js","/assets/link-Ct9nkRTn.js","/assets/login-DEYgWNUo.js","/assets/ping-matrix-MLIc5fTX.js","/assets/reports-7cZ431fF.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BH4DDs0T.js","/assets/servers._serverId-UGmfFT50.js","/assets/servers.index-Ba4KmKlF.js","/assets/settings-BBTgg9SE.js","/assets/ssl-B0Mj2DyH.js","/assets/ssl-Cx12tc_-.js","/assets/tooltip-BraHW7Vl.js","/assets/traffic-CyMy7QGS.js","/assets/useMatch-Bijd88RT.js","/assets/useRefreshAll-NSJUy84D.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
