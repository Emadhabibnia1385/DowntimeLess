const CACHE = "downtimeless-a554b90516";
const FILES = ["/assets/ChoiceFields-BWgaBPdF.js","/assets/CopyButton-AORxvhxl.js","/assets/DataTable-BuQzT6Dk.js","/assets/Loadable-DzEr2lOz.js","/assets/Modal-BkzX2s1w.js","/assets/NumberField-KR5LD95E.js","/assets/StaticTable-BA4U6E23.js","/assets/StatusChip-C7JQi7tA.js","/assets/SwitchField-Db6TtDrR.js","/assets/_app-DdwvHMoL.js","/assets/_app-fW3nK5XS.js","/assets/accent-9pZLV5-s.js","/assets/account-DMqrhbFt.js","/assets/api-keys-Dukq6vW6.js","/assets/auth-D-UF2vmF.js","/assets/color-MwUzspQ2.js","/assets/index-DB0zNNXj.css","/assets/index-DSWesuuI.js","/assets/issues-CQWDs35P.js","/assets/issues-DurP7udG.js","/assets/lazyRouteComponent-gDyahCde.js","/assets/link-C5oUCD3U.js","/assets/login-ByRBo2ty.js","/assets/members-CA3ptTgY.js","/assets/members-DGWvZBd1.js","/assets/panel-CBJGEGXM.js","/assets/panel-CYFIJuMm.js","/assets/ping-matrix-iv4cWNgL.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-CEFN1R7F.js","/assets/servers._serverId-DG_SLNxC.js","/assets/servers.index-JlvVWfMF.js","/assets/settings-goMG8gHw.js","/assets/ssl-BMIzrndX.js","/assets/ssl-DaW1yn_f.js","/assets/tooltip-Dp0fPant.js","/assets/traffic-B7sWBSqd.js","/assets/traffic-BMltBXUu.js","/assets/useMatch-B9l18W05.js","/assets/useRefreshAll-cLOsKZ05.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
