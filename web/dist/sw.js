const CACHE = "downtimeless-2f1b98bcc5";
const FILES = ["/assets/DataTable-CZbN_t2l.js","/assets/IpText-Dc4q7ZY4.js","/assets/KeyValueList-Bt3CzxNp.js","/assets/Loadable-BLV_khMv.js","/assets/Modal-D8sCaqCw.js","/assets/NumberField-BruG_6ef.js","/assets/PageHeader-5CRyNIbo.js","/assets/SectionCard-CarG68IM.js","/assets/StatCard-jV5JmQnw.js","/assets/StatusChip-evDRo6yP.js","/assets/_app-BbHRz4tL.js","/assets/_app-BtwRO2_z.js","/assets/accent-9pZLV5-s.js","/assets/account-BduRUmnu.js","/assets/api-keys-BC0UkIAi.js","/assets/auth-BXNgsLEK.js","/assets/color-MwUzspQ2.js","/assets/index-C7fiJNL3.css","/assets/index-z3ms_3du.js","/assets/issues--C5qPA1L.js","/assets/issues-rT9Uocf3.js","/assets/lazyRouteComponent-DVz1LR-L.js","/assets/link-CEYEPj2_.js","/assets/login-JVbLXZqS.js","/assets/overview-DFtenofG.js","/assets/ping-matrix-CQKbtEom.js","/assets/radio-group-CN7_TFu2.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-VQWalqmj.js","/assets/servers._serverId-Bta1zoBn.js","/assets/servers.index-tdXjrrbs.js","/assets/settings-BnCuhyav.js","/assets/settings-HgdMCHhT.js","/assets/ssl-DdsjEX3O.js","/assets/ssl-vO8i_dB1.js","/assets/table.styles-Cxt-axV2.js","/assets/tooltip-CBcpFuk4.js","/assets/useDocumentTitle-P-S6EHOY.js","/assets/useLocalizedStringFormatter-B498XeB5.js","/assets/useMatch-CZBHM3-z.js","/assets/useRefreshAll-HTeyvwI3.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
