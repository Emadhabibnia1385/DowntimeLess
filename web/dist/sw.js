const CACHE = "downtimeless-dbfe3436fc";
const FILES = ["/assets/DataTable-DMmIIUK3.js","/assets/KeyValueList-DaVJKhVH.js","/assets/Loadable-CMYMbxHp.js","/assets/Modal-DKmJJ4db.js","/assets/NumberField-4SrzeQ5M.js","/assets/PageHeader-2-PWgYSN.js","/assets/SectionCard-BUTNIJmT.js","/assets/StatCard-ChjM1AVQ.js","/assets/StatusChip-DDsV6FrD.js","/assets/_app-B2yq_edE.js","/assets/_app-JHMsHY93.js","/assets/accent-9pZLV5-s.js","/assets/account-B33PnABB.js","/assets/api-keys-BESyH6Lm.js","/assets/auth-qO8mHje7.js","/assets/color-MwUzspQ2.js","/assets/index-BMznSgw6.js","/assets/index-DhIU9AVV.css","/assets/issues-Bcbm8mQW.js","/assets/issues-eS6hNWSx.js","/assets/lazyRouteComponent-Ckcv0NZo.js","/assets/link-CBec-ACw.js","/assets/login-C5617ZT9.js","/assets/overview-Ch1CSUJI.js","/assets/ping-matrix-BIFMCdxu.js","/assets/radio-group-CCVr1qyg.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-B_vG8lEE.js","/assets/servers._serverId--n_6Z9vi.js","/assets/servers.index-DwM7RIAh.js","/assets/settings-BEdDbsZ_.js","/assets/settings-Cgel5-kU.js","/assets/ssl-B_nG9Der.js","/assets/ssl-DIuZkLKw.js","/assets/table.styles-Rf_hiDef.js","/assets/tooltip-sJpdX4Iu.js","/assets/useDocumentTitle-B6NvE5wy.js","/assets/useLocalizedStringFormatter-CdNA9jXm.js","/assets/useMatch-C1y-lQyz.js","/assets/useRefreshAll-CbnN-l0A.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
