const CACHE = "downtimeless-8e5f73382e";
const FILES = ["/assets/ChoiceFields-B43nP8N5.js","/assets/CopyButton-DdSKEYh1.js","/assets/DataTable-OxkkXVdQ.js","/assets/Loadable-Bwh8q_oH.js","/assets/SelectField-BE61pkAI.js","/assets/StaticTable-Btz_81ew.js","/assets/StatusChip-B8Uf0ZHD.js","/assets/_app-BBjj9CiF.js","/assets/_app-e0kOuGCH.js","/assets/accent-9pZLV5-s.js","/assets/account-BpM4DMQB.js","/assets/api-keys-CzYallrq.js","/assets/auth-9gfv7x-7.js","/assets/color-MwUzspQ2.js","/assets/index-BmuptR7t.js","/assets/index-wpPw66NR.css","/assets/issues-BkpzVPhv.js","/assets/issues-EzXNDbl_.js","/assets/lazyRouteComponent-DvcFmLSH.js","/assets/link-SC1oTJGx.js","/assets/login-DeHLNMMI.js","/assets/members-DHwT1ey_.js","/assets/members-DwOFEo15.js","/assets/ping-matrix-_EMMubIb.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-CgSe7zN-.js","/assets/servers._serverId-BCz6DDHA.js","/assets/servers.index-BdEZiNU1.js","/assets/settings-D-vV89Ct.js","/assets/ssl-7DpBGMA5.js","/assets/ssl-B5hWq6NE.js","/assets/tooltip-CYs3v6bq.js","/assets/traffic-BQjdejCb.js","/assets/traffic-Bmhch3qP.js","/assets/useMatch-RkeCuxIl.js","/assets/useRefreshAll-4gFuLmMW.js","/assets/useSlot-DIEkaCDq.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
