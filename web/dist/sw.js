const CACHE = "downtimeless-cc3a7bc061";
const FILES = ["/assets/DataTable-BeyPb6Q_.js","/assets/KeyValueList-P-W8gMaj.js","/assets/Loadable-DgQFQPSN.js","/assets/Modal-BQYhIo6r.js","/assets/NumberField-DsbgzPMN.js","/assets/PageHeader-CHtBJtC8.js","/assets/SectionCard-BaqAflY2.js","/assets/StatCard-DQJhhSBF.js","/assets/StatusChip-CLjhTKYZ.js","/assets/_app-CUK8HYWp.js","/assets/_app-cjhcheSm.js","/assets/accent-9pZLV5-s.js","/assets/account-CH1fIPk8.js","/assets/api-keys-zYH0tvTv.js","/assets/auth-Q4s50gLs.js","/assets/color-MwUzspQ2.js","/assets/index-CFozAWYf.js","/assets/index-KROt15EW.css","/assets/issues-DNncBTYv.js","/assets/issues-qLUOAd9E.js","/assets/lazyRouteComponent-CRwgo9Cq.js","/assets/link-DFtxb_kZ.js","/assets/login-C7AFs14k.js","/assets/overview-DYq3CJjO.js","/assets/ping-matrix-Bjb2NAbx.js","/assets/radio-group-CnLltwiH.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BlfdjqtE.js","/assets/servers._serverId-Xc4AmgKW.js","/assets/servers.index-DRuLMpzQ.js","/assets/settings-CKfPKm6c.js","/assets/settings-CpkCvJNl.js","/assets/ssl-DUKHSPkh.js","/assets/ssl-DhLA7aXC.js","/assets/table.styles-DyxzMeL_.js","/assets/tooltip-Db8ATpoa.js","/assets/useDocumentTitle-CAIF-UHV.js","/assets/useLocalizedStringFormatter-CmUKJL2N.js","/assets/useMatch-DcQEkvDa.js","/assets/useRefreshAll-DQrhDaJQ.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
