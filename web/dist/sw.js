const CACHE = "downtimeless-3a783d55e0";
const FILES = ["/assets/ChoiceFields-_4rB8VNY.js","/assets/CopyButton-BRZeulSp.js","/assets/DataTable-CrrQnYxi.js","/assets/Loadable-r7BylvL-.js","/assets/SelectField-xzj_MRYQ.js","/assets/StaticTable-oDrE_g3c.js","/assets/StatusChip-CIfgcLB2.js","/assets/Tabs-DmsZrxBN.js","/assets/_app-D3ioSA2M.js","/assets/_app-DhL5GNZk.js","/assets/accent-9pZLV5-s.js","/assets/account-BHOZevV6.js","/assets/api-keys-BOfrrYtB.js","/assets/auth-CQjSjyLW.js","/assets/color-MwUzspQ2.js","/assets/index-C32o0W4j.js","/assets/index-UkVgXYI8.css","/assets/issues-CnpMgiFN.js","/assets/issues-Cx09uKlG.js","/assets/lazyRouteComponent-MMgh_eWQ.js","/assets/link-C5kQnAGi.js","/assets/login-BvcCBYYx.js","/assets/members-BBOdUuR1.js","/assets/members-BHBJnCV_.js","/assets/ping-matrix-Cq0pNFlj.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-CJ3z0deN.js","/assets/servers._serverId-DcJTmjzT.js","/assets/servers.index-B3sBNaeP.js","/assets/settings-V7GL3bN_.js","/assets/ssl-CVsTI6vn.js","/assets/ssl-DbpADyhP.js","/assets/tooltip-D9-9ED4r.js","/assets/traffic-9nMij3p9.js","/assets/traffic-Dc9jDiA0.js","/assets/useMatch-DInOtuMV.js","/assets/useRefreshAll-Dy3p7GEn.js","/assets/useSlot-B9_MDxvd.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
