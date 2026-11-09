const CACHE = "downtimeless-84a036542e";
const FILES = ["/assets/ChoiceFields-YoDm5EER.js","/assets/CopyButton-FRan56Yr.js","/assets/DataTable-S2Qwlu-7.js","/assets/Loadable-BNBANquQ.js","/assets/Modal-BNwmwzWs.js","/assets/NumberField-7gNOGWkW.js","/assets/StaticTable-LoDj71Pc.js","/assets/StatusChip-B34OZMig.js","/assets/SwitchField-D_Te9Ls0.js","/assets/_app-CWm8NP9J.js","/assets/_app-DHZK_zjW.js","/assets/accent-9pZLV5-s.js","/assets/account-BZWxLnA-.js","/assets/api-keys-DlTqHtQt.js","/assets/auth-CQVk7PBU.js","/assets/color-MwUzspQ2.js","/assets/index-CZPOkKhv.css","/assets/index-rS7rhJaS.js","/assets/issues-BqFy7qoh.js","/assets/issues-DTGvGu5y.js","/assets/lazyRouteComponent-CDYTa34W.js","/assets/link-CCEuYMnC.js","/assets/login-DJOK8CPT.js","/assets/members-B9HpFvlW.js","/assets/members-mLsaKLPp.js","/assets/panel-D--EEd7y.js","/assets/panel-zSjdkxJC.js","/assets/ping-matrix-BGltYkY7.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BlNk4iQk.js","/assets/servers._serverId-loKdKklk.js","/assets/servers.index-DbWB2wfS.js","/assets/settings-B7tqVF9t.js","/assets/ssl-4l6tFkX6.js","/assets/ssl-CBwLbrzx.js","/assets/tooltip-3cMRU2A4.js","/assets/traffic-IOe1JQCu.js","/assets/traffic-U_ZhQ1sY.js","/assets/useMatch-CcQEGuh7.js","/assets/useRefreshAll-C7PkZUk3.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
