const CACHE = "downtimeless-5963caa1ff";
const FILES = ["/assets/CopyButton-BK40AZ-R.js","/assets/DataTable-CfSl4v1C.js","/assets/Loadable-CeOx9VWT.js","/assets/Modal-BveDvMME.js","/assets/StaticTable-CEXuMt-D.js","/assets/Tabs-BhAv48WM.js","/assets/_app-CB08m17Q.js","/assets/_app-CrhzHLDM.js","/assets/accent-9pZLV5-s.js","/assets/account-BuvJoYeW.js","/assets/api-keys-loCa6mhE.js","/assets/auth-_snTVdAz.js","/assets/color-MwUzspQ2.js","/assets/index-DIdeCHJJ.css","/assets/index-DT19OY67.js","/assets/issues-C8cgnuan.js","/assets/issues-DJDARtXC.js","/assets/lazyRouteComponent-dUlUZKEr.js","/assets/link-DaCp508t.js","/assets/login-BtLQ-MpY.js","/assets/ping-matrix-6Ih1_r25.js","/assets/reports-D6qbYOmc.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-D6RI6M5f.js","/assets/servers._serverId-DGaOIxgU.js","/assets/servers.index-BfmXXuoj.js","/assets/settings-r-wGHMr0.js","/assets/ssl-BI6Pn0p0.js","/assets/ssl-C3V9mEk6.js","/assets/tooltip-BDaqhEXT.js","/assets/traffic-D_jEoAXz.js","/assets/useMatch-BbEwQ7_j.js","/assets/useRefreshAll-BnhN9ahv.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
