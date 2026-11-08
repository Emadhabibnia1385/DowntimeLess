const CACHE = "downtimeless-028147b2d6";
const FILES = ["/assets/DataTable-CY7kXyvd.js","/assets/KeyValueList-BHifLpHl.js","/assets/Loadable-B21mCBF4.js","/assets/Modal-DLZc83JY.js","/assets/NumberField-B0S_Jv1R.js","/assets/PageHeader-CoILrydv.js","/assets/SectionCard-BnR4zMsi.js","/assets/StatCard-Blp_YzYs.js","/assets/StatusChip-CCwdWMId.js","/assets/_app-BUCtJkTw.js","/assets/_app-Pct7P8uE.js","/assets/accent-9pZLV5-s.js","/assets/account-BgZVEKd7.js","/assets/api-keys-CMPGNyr7.js","/assets/auth-CsM5-Jdv.js","/assets/color-MwUzspQ2.js","/assets/index-BlDbfY2e.js","/assets/index-C8LMMkZQ.css","/assets/issues-BcdbC4Xb.js","/assets/issues-DpWJFKGR.js","/assets/lazyRouteComponent-JSe0DltV.js","/assets/link-Cgwo_GdY.js","/assets/login-BtKAWqaG.js","/assets/overview-Cp9EGRGW.js","/assets/ping-matrix-BXetfVGa.js","/assets/radio-group-8qfjT_3h.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-C9ynOpMp.js","/assets/servers._serverId-CmFJGrj0.js","/assets/servers.index-Cpa6UPMY.js","/assets/settings-CgvNmIqx.js","/assets/settings-DvhCbEe7.js","/assets/ssl-BqEPrbZ3.js","/assets/ssl-LccPmULf.js","/assets/table.styles-DGFHvwqe.js","/assets/tooltip-BBUu6l1c.js","/assets/useDocumentTitle-Dn_1o-MA.js","/assets/useLocalizedStringFormatter-DFfBrbvh.js","/assets/useMatch-k2eDARPm.js","/assets/useRefreshAll-4sd7wF0j.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
