const CACHE = "downtimeless-a2ba08ac54";
const FILES = ["/assets/DataTable-BZYuQlNW.js","/assets/KeyValueList-BHLm2kHY.js","/assets/Loadable-BZRMlIsp.js","/assets/Modal-4p8Q84oG.js","/assets/NumberField-4JTwBtg-.js","/assets/PageHeader-IPzDOD6C.js","/assets/SectionCard-C87Z4yFe.js","/assets/StatCard-BiNP9CRY.js","/assets/StatusChip-DL4GMTFU.js","/assets/_app-CVFwX2UD.js","/assets/_app-DzmsQS0P.js","/assets/accent-9pZLV5-s.js","/assets/account-Bjb0OGkS.js","/assets/api-keys-Crc-YaYu.js","/assets/auth-D1XqoBRN.js","/assets/color-MwUzspQ2.js","/assets/index-DtCpfQyA.js","/assets/index-KROt15EW.css","/assets/issues-EPnqeXAj.js","/assets/issues-FypHJxrB.js","/assets/lazyRouteComponent-CmvvoUcl.js","/assets/link-DFX4Ot43.js","/assets/login-Cbm_bjJK.js","/assets/overview-CmH6WGp7.js","/assets/ping-matrix-BUI0iIS2.js","/assets/radio-group-CTGZfvui.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BVCmVnBr.js","/assets/servers._serverId-DQp3AoGd.js","/assets/servers.index-DaAOUQ9L.js","/assets/settings-C5D01dQx.js","/assets/settings-DUAFPjDJ.js","/assets/ssl-Cr3Dhx_c.js","/assets/ssl-CxW6sIok.js","/assets/table.styles-CYY8QrgF.js","/assets/tooltip-BwW3Gm0v.js","/assets/useDocumentTitle-CculioeC.js","/assets/useLocalizedStringFormatter-Cc0nxwnm.js","/assets/useMatch-BbxoVuLi.js","/assets/useRefreshAll-DG-wmoSI.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
