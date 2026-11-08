const CACHE = "downtimeless-9323119ad8";
const FILES = ["/assets/DataTable-Bbcyn03Y.js","/assets/IpText-DfI_jmmc.js","/assets/KeyValueList-CelmaobH.js","/assets/Loadable-DQpOzH5O.js","/assets/Modal-ByKL0USW.js","/assets/NumberField-T9o4XdIz.js","/assets/PageHeader-D2ZS1kkz.js","/assets/SectionCard-BHMRnes6.js","/assets/StatCard-DVjNkdtg.js","/assets/StatusChip-DvTLpIE5.js","/assets/_app-Cdr8V9g7.js","/assets/_app-DiQE1qKQ.js","/assets/accent-9pZLV5-s.js","/assets/account-DWU2IPaR.js","/assets/api-keys-yHe0oVGH.js","/assets/auth-DF2pBUDc.js","/assets/color-MwUzspQ2.js","/assets/index-BIjVWVgP.js","/assets/index-CW6nUDkh.css","/assets/issues-CGCK_OtA.js","/assets/issues-Nuefstsb.js","/assets/lazyRouteComponent-C4nVKesI.js","/assets/link-BYe52MHG.js","/assets/login-Bh8UeRl7.js","/assets/overview-CukBC4Ak.js","/assets/ping-matrix-C7QUIFGm.js","/assets/radio-group-D8sMauRo.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-aFs7eGk3.js","/assets/servers._serverId-DR3Jys7Q.js","/assets/servers.index-BSgCzJwM.js","/assets/settings-B8CJNbrF.js","/assets/settings-B9jHvb2V.js","/assets/ssl-96hmVQ0h.js","/assets/ssl-C0NprjUV.js","/assets/table.styles-BZnJ1br1.js","/assets/tooltip-Cy2xGpxl.js","/assets/useDocumentTitle-CueIyN1G.js","/assets/useLocalizedStringFormatter-J1ne696Q.js","/assets/useMatch-EKqrnHAY.js","/assets/useRefreshAll-DDNryLdg.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
