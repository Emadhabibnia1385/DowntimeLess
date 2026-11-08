const CACHE = "downtimeless-d17ddd64ca";
const FILES = ["/assets/CollectionBuilder-CAmT0F76.js","/assets/ConfirmDialog-cVcrhlQN.js","/assets/CopyButton-dkqB9ntq.js","/assets/DataTable-7fvLBpQK.js","/assets/KeyValueList-C_BdmV6p.js","/assets/Loadable-CyKPiqnV.js","/assets/Modal-BWg-fW9P.js","/assets/NumberField-BML_bZtG.js","/assets/StaticTable-B6USjmMK.js","/assets/StatusChip-CvX23eLZ.js","/assets/_app-DOrkVYVv.js","/assets/_app-Dy84NgGl.js","/assets/accent-9pZLV5-s.js","/assets/account-kbVY7m9e.js","/assets/api-keys-BBOR_z9s.js","/assets/auth-B99XgZGl.js","/assets/color-MwUzspQ2.js","/assets/index-65FUz5mT.css","/assets/index-DGhK7t3c.js","/assets/issues-DR2x1-L5.js","/assets/issues-Tu6o_5KB.js","/assets/lazyRouteComponent-BH9zbDKR.js","/assets/link-C-xGx3wR.js","/assets/login-CMdO2NFt.js","/assets/number-DXh_SLeu.js","/assets/overview-CvfC28oT.js","/assets/ping-matrix-B5IJD9Bw.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-D07p8K_O.js","/assets/servers._serverId-Bd1T6oKZ.js","/assets/servers.index-Cj2yhSG8.js","/assets/settings-3UAclVIK.js","/assets/ssl-0vZFejOi.js","/assets/ssl-DRNjv4E_.js","/assets/tooltip-CAYS9vDh.js","/assets/useDocumentTitle-DN33Fnri.js","/assets/useLoadMoreSentinel-DNlyDZ4i.js","/assets/useMatch-LmbqB-tL.js","/assets/useRefreshAll-ea-zz5qN.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
