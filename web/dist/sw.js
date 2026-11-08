const CACHE = "downtimeless-80ca060681";
const FILES = ["/assets/DataTable-BAQewkYr.js","/assets/KeyValueList-DjZZkW_j.js","/assets/Loadable-Cyi4Jrk_.js","/assets/Modal-drE392qy.js","/assets/NumberField-CzXp08Qu.js","/assets/PageHeader-B7J8FUgC.js","/assets/SectionCard-Bkg44XUX.js","/assets/StatCard-CUdvAA4H.js","/assets/StatusChip-DApMQgei.js","/assets/_app-BU_9upcQ.js","/assets/_app-C61-R5Te.js","/assets/accent-9pZLV5-s.js","/assets/account-y3g-F4Zk.js","/assets/api-keys-BSWZPGvU.js","/assets/auth-1PTtdV4s.js","/assets/color-MwUzspQ2.js","/assets/index-BwtZB5tg.css","/assets/index-dCTmI6Nb.js","/assets/issues-0t7RyOZg.js","/assets/issues-DJ0YC97W.js","/assets/lazyRouteComponent-DYrXYI4s.js","/assets/link-HgbpVqe0.js","/assets/login-CrTdDPPm.js","/assets/overview-BZvKP_mJ.js","/assets/ping-matrix-CA8slA8w.js","/assets/radio-group-BQbUX90V.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-NWNxj9fO.js","/assets/servers._serverId-DmnRLeFZ.js","/assets/servers.index-DP-UnJtL.js","/assets/settings-BNGI83KF.js","/assets/settings-CsuZ9u7g.js","/assets/ssl-3bKGf_5T.js","/assets/ssl-DH9XMVjy.js","/assets/table.styles-CV-9UXcd.js","/assets/tooltip-B7xdHQyT.js","/assets/useDocumentTitle-CHD73Gh6.js","/assets/useLocalizedStringFormatter-vsv3sKNS.js","/assets/useMatch-CJ3h78Ey.js","/assets/useRefreshAll-ByIf2Hik.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
