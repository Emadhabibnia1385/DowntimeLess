const CACHE = "downtimeless-56d6e2b58d";
const FILES = ["/assets/ChoiceFields-DcdrS7-7.js","/assets/CopyButton-D2v9j6PW.js","/assets/DataTable-C16TfSpH.js","/assets/Loadable-BMC96AcL.js","/assets/SelectField-BsfrXQ-d.js","/assets/StaticTable-DbscHLSE.js","/assets/StatusChip-DhmhdKRe.js","/assets/Tabs-B227qU6f.js","/assets/_app-7YMC-nm9.js","/assets/_app-BZh8lPVH.js","/assets/accent-9pZLV5-s.js","/assets/account-DsoDjZWd.js","/assets/api-keys-BYZwBeJO.js","/assets/auth-D6BkpxVf.js","/assets/color-MwUzspQ2.js","/assets/index-CAqfXHZY.js","/assets/index-CUJuyStK.css","/assets/issues-Eu8vRde7.js","/assets/issues-z0C8jEYE.js","/assets/lazyRouteComponent-DxLe_C56.js","/assets/link-CbBLydbW.js","/assets/login-DsklF2dA.js","/assets/members-Cgv81Q8f.js","/assets/members-xotcte8Z.js","/assets/ping-matrix-BYMuwu1m.js","/assets/reports-DfWXNZb3.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-CORDFm6S.js","/assets/servers._serverId-CTHXjWiS.js","/assets/servers.index-DCplgmwp.js","/assets/settings-BJugnQPC.js","/assets/ssl-BsNLg1SW.js","/assets/ssl-DBOlwf65.js","/assets/tooltip-C0-qWpel.js","/assets/traffic-B5z6BTx0.js","/assets/traffic-BXJJKLMI.js","/assets/useMatch-B-2Hset6.js","/assets/useRefreshAll--aBPBCeU.js","/assets/useSlot-C1BTrFFR.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
