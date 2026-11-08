const CACHE = "downtimeless-39ef82e53c";
const FILES = ["/assets/CollectionBuilder-CyhvAfZH.js","/assets/ConfirmDialog-BEZ6bo74.js","/assets/DataTable-TUTy-Alo.js","/assets/IpText-aq9UpEDY.js","/assets/KeyValueList-CDzErtK2.js","/assets/Loadable-BVii1XFw.js","/assets/Modal-BV5EH22n.js","/assets/NumberField-DtcmKWYV.js","/assets/PageHeader-BFB9GoMP.js","/assets/SectionCard-pWlL5E8p.js","/assets/StatCard--46OoHkn.js","/assets/StatusChip-BC13ZiX3.js","/assets/_app-D5IXKzv3.js","/assets/_app-MRcVnlJs.js","/assets/accent-9pZLV5-s.js","/assets/account-CBmcV8oa.js","/assets/api-keys-CIlkLBob.js","/assets/auth-Bw92oOw8.js","/assets/color-MwUzspQ2.js","/assets/index-C8_vTZ0K.js","/assets/index-tJvLFFsr.css","/assets/issues-C0Ka0Y-m.js","/assets/issues-DEl6u8CD.js","/assets/lazyRouteComponent-CXoVCQz5.js","/assets/link-D87Z-_Fa.js","/assets/login-6btOdwrv.js","/assets/number-D6xxqgMK.js","/assets/overview-BpEMONLX.js","/assets/ping-matrix-DQgWakrg.js","/assets/radio-group-BdV8JPMq.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BwPHDogD.js","/assets/servers._serverId-IkPDFkzp.js","/assets/servers.index-2bFnsYR_.js","/assets/settings-B_wcGC9G.js","/assets/settings-VJ_XjrQF.js","/assets/ssl-DHGGIys7.js","/assets/ssl-hK1w3Tgr.js","/assets/tooltip-DEoZPic5.js","/assets/useDocumentTitle-mvwqZiux.js","/assets/useEvent-DDftmavX.js","/assets/useLocalizedStringFormatter-CXGTFrF9.js","/assets/useMatch-DJjQeP-v.js","/assets/useRefreshAll-CrOuhHpV.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
