const CACHE = "downtimeless-96e0f587f4";
const FILES = ["/assets/ChoiceFields-D5lGGRY1.js","/assets/CopyButton-DVdXFd2F.js","/assets/DataTable-9q2g4B7H.js","/assets/Loadable-BL9aDXaH.js","/assets/Modal-BrayOO2j.js","/assets/NumberField-CwEhfm--.js","/assets/StaticTable-CyrO4yj1.js","/assets/StatusChip-n58EqGvC.js","/assets/SwitchField-DS-glke6.js","/assets/_app-BAFgDapN.js","/assets/_app-DrEq6A-x.js","/assets/accent-9pZLV5-s.js","/assets/account-BuLPJTqJ.js","/assets/api-keys-C0snmkrS.js","/assets/auth-DKORoeqt.js","/assets/color-MwUzspQ2.js","/assets/index-CZPOkKhv.css","/assets/index-DYqOT24a.js","/assets/issues-Csquwa0h.js","/assets/issues-DytmqtAd.js","/assets/lazyRouteComponent-BxB2nYvo.js","/assets/link-uCQmXF3R.js","/assets/login-KmLSUtCw.js","/assets/members-CyQRFdiC.js","/assets/members-dbFNGTgb.js","/assets/panel-6XRGpPT_.js","/assets/panel-LU6gU71S.js","/assets/ping-matrix-jkYHR43w.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-XkATkCg4.js","/assets/servers._serverId-BBokR8Yd.js","/assets/servers.index-C_FKIITS.js","/assets/settings-muM65BP1.js","/assets/ssl-CXho_P4N.js","/assets/ssl-DWIp6mLS.js","/assets/tooltip-0tmjaC6y.js","/assets/traffic-Dom_maIi.js","/assets/traffic-M5mU1-Cp.js","/assets/useMatch-CHNrWAu8.js","/assets/useRefreshAll-B2EQH-mE.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
