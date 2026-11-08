const CACHE = "downtimeless-cb9fdd7ac8";
const FILES = ["/assets/DataTable-C5zjfFRv.js","/assets/IpText-HVc595xO.js","/assets/KeyValueList-DhgLZnmo.js","/assets/Loadable-Cvn2LiKL.js","/assets/Modal-qcsv8qPS.js","/assets/NumberField-Dd_ZPTOM.js","/assets/PageHeader-22s48VEV.js","/assets/SectionCard-Bq7sv9Yp.js","/assets/StatCard-CQ_yLKPs.js","/assets/StatusChip-BubEy-NX.js","/assets/_app-DWfn5ZgY.js","/assets/_app-DwblTe6f.js","/assets/accent-9pZLV5-s.js","/assets/account-DW9J1PHf.js","/assets/api-keys-Bqu9-gDz.js","/assets/auth-ypcTiL53.js","/assets/color-MwUzspQ2.js","/assets/index-C1ro3jor.js","/assets/index-C7fiJNL3.css","/assets/issues-BRyQsl-n.js","/assets/issues-ym0XCI8A.js","/assets/lazyRouteComponent-Ci4eDNY0.js","/assets/link-C-Th1FmX.js","/assets/login-DvAGipEN.js","/assets/overview-HkcCDxMg.js","/assets/ping-matrix-DZU7uFIr.js","/assets/radio-group-CSaJyWES.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BbeFFmuR.js","/assets/servers._serverId-DwNdSTD4.js","/assets/servers.index-sfyf7hnG.js","/assets/settings-Bl9XxJ6f.js","/assets/settings-DNUbjgOn.js","/assets/ssl-By3gaBr_.js","/assets/ssl-DGP3rH_q.js","/assets/table.styles-DzKVFOj6.js","/assets/tooltip-CqHqLYwe.js","/assets/useDocumentTitle-di1__079.js","/assets/useLocalizedStringFormatter-BqLqWTKl.js","/assets/useMatch-BXR1qnMw.js","/assets/useRefreshAll-DyQbRP9C.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
