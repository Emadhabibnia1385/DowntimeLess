const CACHE = "downtimeless-3a9c2f1fa0";
const FILES = ["/assets/CollectionBuilder-yXTvrFIF.js","/assets/ConfirmDialog-DoAdj1BJ.js","/assets/CopyButton-C8rS4L9o.js","/assets/DataTable-DzIEMBCV.js","/assets/KeyValueList-C6j_9Lba.js","/assets/Loadable-BOjr9V-6.js","/assets/Modal-YrrIwrW8.js","/assets/StatusChip-BG-gTiBK.js","/assets/_app-BheWNyDL.js","/assets/_app-C6JGuoc4.js","/assets/accent-9pZLV5-s.js","/assets/account-C1WOPVq2.js","/assets/api-keys-FglDTVNz.js","/assets/auth-Bez12O0t.js","/assets/color-MwUzspQ2.js","/assets/index-95TQEuCc.js","/assets/index-CGeTODik.css","/assets/issues-CiyduNOZ.js","/assets/issues-Du6pu1Td.js","/assets/lazyRouteComponent-rQO5-yz-.js","/assets/link-BJHSt5Zo.js","/assets/login-CQzpSH2m.js","/assets/number-xiLoPT49.js","/assets/overview-Sor06C5P.js","/assets/ping-matrix-Ca2mh5UF.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-CNTF6mnV.js","/assets/servers-mqm0I9tR.js","/assets/servers._serverId-DePcOlgB.js","/assets/servers.index-dkGLHj-v.js","/assets/ssl-D23dLBS8.js","/assets/ssl-DxteheGo.js","/assets/tooltip-D33bKru7.js","/assets/useDocumentTitle-DxsN5MYI.js","/assets/useListState-XQXZYTb7.js","/assets/useLoadMoreSentinel-eYWTxTWh.js","/assets/useMatch-De6fC6-7.js","/assets/useRefreshAll-D5yFLDsX.js","/assets/useSlot-Dna7fS7Z.js","/assets/useToggleState-BuPExfYQ.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
