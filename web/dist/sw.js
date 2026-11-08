const CACHE = "downtimeless-14cfe0cc8b";
const FILES = ["/assets/DataTable-zS808d1d.js","/assets/KeyValueList-P-W8gMaj.js","/assets/Loadable-DgQFQPSN.js","/assets/Modal-D0aEQvLJ.js","/assets/NumberField-CXha6eIA.js","/assets/PageHeader-CHtBJtC8.js","/assets/SectionCard-BaqAflY2.js","/assets/StatCard-DQJhhSBF.js","/assets/StatusChip-CLjhTKYZ.js","/assets/_app-D7-KzVet.js","/assets/_app-DmvAge6o.js","/assets/accent-9pZLV5-s.js","/assets/account-eKYYBdHn.js","/assets/api-keys-BNEVqa77.js","/assets/auth-NQ2QR5q7.js","/assets/color-MwUzspQ2.js","/assets/index-BGTXCQZ3.js","/assets/index-Do6istVX.css","/assets/issues-DNncBTYv.js","/assets/issues-qLUOAd9E.js","/assets/lazyRouteComponent-CEoXsnJF.js","/assets/link-DuVObu5Q.js","/assets/login-DcPXsWTj.js","/assets/overview-DYq3CJjO.js","/assets/ping-matrix-wlO1up7d.js","/assets/radio-group-PMbayTUP.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BXe9EOfi.js","/assets/servers._serverId-lNfQz9F7.js","/assets/servers.index-d-xzGFvf.js","/assets/settings-CZK60w7u.js","/assets/settings-DQJXbieh.js","/assets/ssl-BhPrFm43.js","/assets/ssl-CQ7_3fH2.js","/assets/table.styles-DyxzMeL_.js","/assets/tooltip-9Dt6tb23.js","/assets/useDocumentTitle-CAIF-UHV.js","/assets/useLocalizedStringFormatter-CmUKJL2N.js","/assets/useMatch-CPuCMHqr.js","/assets/useRefreshAll-DQrhDaJQ.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
