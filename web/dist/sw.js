const CACHE = "downtimeless-242fb08920";
const FILES = ["/assets/CopyButton-DLuu6Rlp.js","/assets/DataTable-DpoIB3-a.js","/assets/Loadable-3aJy5-9V.js","/assets/Modal-BYTP542v.js","/assets/StaticTable-COYoVlBN.js","/assets/Tabs-Cb5FWayr.js","/assets/_app-10jnh3f_.js","/assets/_app-CJv5Fr0a.js","/assets/accent-9pZLV5-s.js","/assets/account-Dx8AmnkI.js","/assets/api-keys-BO8l-PW5.js","/assets/auth-B0jseRGA.js","/assets/color-MwUzspQ2.js","/assets/index-Bk-Uw5lO.css","/assets/index-Dm4-s-Ri.js","/assets/issues-DLyQPV7a.js","/assets/issues-DtzWTKJX.js","/assets/lazyRouteComponent-B7xOCYO7.js","/assets/link-Ct9nkRTn.js","/assets/login-DgKk0slr.js","/assets/ping-matrix-CwwKUKh4.js","/assets/reports-laAxpTde.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-CuyJQHeb.js","/assets/servers._serverId-BtD6GShZ.js","/assets/servers.index-Dh3x5Qsd.js","/assets/settings-BBTgg9SE.js","/assets/ssl-C_z3YfjN.js","/assets/ssl-D3tUxPqi.js","/assets/tooltip-BraHW7Vl.js","/assets/traffic-D4G4FJNx.js","/assets/useMatch-Bijd88RT.js","/assets/useRefreshAll-NSJUy84D.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
