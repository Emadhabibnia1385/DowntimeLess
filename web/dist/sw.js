const CACHE = "downtimeless-473bf5edff";
const FILES = ["/assets/ChoiceFields-5uqZXKwi.js","/assets/CopyButton-CIJb-kgf.js","/assets/DataTable-CVUUXSq3.js","/assets/Loadable-B2EYlwE7.js","/assets/Modal-Cpn3agqk.js","/assets/NumberField-rrkn04tC.js","/assets/StaticTable-BnXnyoUC.js","/assets/StatusChip-BQjBtzio.js","/assets/SwitchField-4uEzmYJY.js","/assets/_app-BIi1q2JB.js","/assets/_app-Bu_4NQQQ.js","/assets/accent-9pZLV5-s.js","/assets/account-HcDViX7D.js","/assets/api-keys-CTuutXXu.js","/assets/auth-E_zoMZNw.js","/assets/color-MwUzspQ2.js","/assets/index-CDc4hfUS.js","/assets/index-CZPOkKhv.css","/assets/issues-CWjcdv5_.js","/assets/issues-DZ7ejri-.js","/assets/lazyRouteComponent-FwTU1_K0.js","/assets/link-CKSCOHl7.js","/assets/login-BRMgOvtQ.js","/assets/members-DGGb4uvg.js","/assets/members-yVn3pBfe.js","/assets/panel-CQ1LwDO-.js","/assets/panel-D6mssVvy.js","/assets/ping-matrix-BhXh63d4.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BiTy-4_6.js","/assets/servers._serverId-BU4KGeOT.js","/assets/servers.index-Bu0W0sgB.js","/assets/settings-BHywKsGP.js","/assets/ssl-BvX1iZ88.js","/assets/ssl-C0VCSLWX.js","/assets/tooltip-DpV9AhhO.js","/assets/traffic-D2BAP9Aw.js","/assets/traffic-vYFKzq8C.js","/assets/useMatch-DDeP5AtU.js","/assets/useRefreshAll-D1vd7pB7.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
