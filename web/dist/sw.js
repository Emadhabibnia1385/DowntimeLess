const CACHE = "downtimeless-d865517b04";
const FILES = ["/assets/CollectionBuilder-Do6NXaHB.js","/assets/ConfirmDialog-Di1dj7Ns.js","/assets/CopyButton-tF1T-lds.js","/assets/DataTable-6jo-SOiy.js","/assets/KeyValueList-BQACPRBs.js","/assets/Loadable-CexyeyuG.js","/assets/Modal-BMcff8V-.js","/assets/NumberField-Cibobvd7.js","/assets/StaticTable-DjL94pBz.js","/assets/StatusChip-CZcTTvV2.js","/assets/_app-DYk2VmNc.js","/assets/_app-Dsl76brz.js","/assets/accent-9pZLV5-s.js","/assets/account-CNzRhe-a.js","/assets/api-keys-Bf52nQnz.js","/assets/auth-B3qauhPY.js","/assets/color-MwUzspQ2.js","/assets/index-B30evGXb.css","/assets/index-D4NudXL0.js","/assets/issues-Cfr9W2aP.js","/assets/issues-jPH7bX6v.js","/assets/lazyRouteComponent-DPEnXD0u.js","/assets/link-DBvML47G.js","/assets/login-u_M9veDv.js","/assets/number-DOsSEAAo.js","/assets/overview-BQgGrX1R.js","/assets/ping-matrix-CLqPz_G6.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-DylmOT1p.js","/assets/servers._serverId-Bw4bpBH3.js","/assets/servers.index-DukNV_EJ.js","/assets/settings-Dng1yJ5G.js","/assets/ssl-CbbfeFSt.js","/assets/ssl-DmiBLstM.js","/assets/tooltip-GegcBl7q.js","/assets/useDocumentTitle-DxXHsOTV.js","/assets/useLoadMoreSentinel-DXodzkq-.js","/assets/useMatch-GHaLs2gE.js","/assets/useRefreshAll-B0YKJ75K.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
