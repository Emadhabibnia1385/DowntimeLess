const CACHE = "downtimeless-41332206d9";
const FILES = ["/assets/ChoiceFields-PoicNc6A.js","/assets/CopyButton-Bjk0YBeR.js","/assets/DataTable-zp8_EV8R.js","/assets/Loadable-CttHfWGv.js","/assets/Modal-Bkr5IK9R.js","/assets/NumberField-CpxVY9qc.js","/assets/StaticTable-BnPx_jp6.js","/assets/StatusChip-BnGnp8vy.js","/assets/SwitchField-Bl7VW4qh.js","/assets/_app-13BTW_b3.js","/assets/_app-CcBWLxEr.js","/assets/accent-9pZLV5-s.js","/assets/account-2Sbf-Qa_.js","/assets/api-keys-BQhnnJpN.js","/assets/auth-DVtymZpF.js","/assets/color-MwUzspQ2.js","/assets/index-CZPOkKhv.css","/assets/index-DOkLI_dY.js","/assets/issues-BQ7lgt3J.js","/assets/issues-o064G6M_.js","/assets/lazyRouteComponent-cwiEbY7Y.js","/assets/link-D3SbAGy6.js","/assets/login-BOCOjcbu.js","/assets/members-BLMNpFKF.js","/assets/members-CKpWTdk0.js","/assets/panel-CgZhf4JO.js","/assets/panel-Dt9AUSlA.js","/assets/ping-matrix-dm-OOXng.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-Z0IRP0A5.js","/assets/servers._serverId-DZUh00gn.js","/assets/servers.index-D_WbqGY5.js","/assets/settings-DuPwIu6w.js","/assets/ssl-BeOTBwlG.js","/assets/ssl-D3vVRryU.js","/assets/tooltip-C-RaMjHW.js","/assets/traffic-C7wO6Uj2.js","/assets/traffic-DNvZEwh0.js","/assets/useMatch-uZVe8Ynt.js","/assets/useRefreshAll-7MIAmQfm.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
