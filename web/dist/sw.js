const CACHE = "downtimeless-7bd3961d4c";
const FILES = ["/assets/CollectionBuilder-pkOWgA-p.js","/assets/CopyButton-BYzAjV8D.js","/assets/DataTable-CJCaOP4B.js","/assets/Loadable-BUvzijn8.js","/assets/Modal-DiTl-Fdc.js","/assets/StaticTable-C4OuUw0A.js","/assets/Tabs-DV1iD0Se.js","/assets/_app-D5VZjOrS.js","/assets/_app-Dhsmtvsw.js","/assets/accent-9pZLV5-s.js","/assets/account-Ch9VCSFi.js","/assets/api-keys-brrjOZpF.js","/assets/auth-D5Ky6cLo.js","/assets/color-MwUzspQ2.js","/assets/index-DaDaAMRf.js","/assets/index-DwVZvt2e.css","/assets/issues-BEiGe6Vo.js","/assets/issues-CRaFw3J4.js","/assets/lazyRouteComponent-DvDSkd2F.js","/assets/link-DLdsqnJX.js","/assets/login-kdUjh0Vp.js","/assets/ping-matrix-BdnEwm-w.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BzRK7xqD.js","/assets/servers._serverId-D9h2gRaG.js","/assets/servers.index-DHsfa6gi.js","/assets/settings-B6vHKjXl.js","/assets/ssl-DKT78OMZ.js","/assets/ssl-DMTkjiIT.js","/assets/tooltip-CZnQE4nN.js","/assets/useMatch-B_vfRn9x.js","/assets/useRefreshAll-BIMGAQQR.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
