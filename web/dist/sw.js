const CACHE = "downtimeless-e4c1746d9b";
const FILES = ["/assets/ChoiceFields-DNW_7oJV.js","/assets/CopyButton-CKjDWJhJ.js","/assets/DataTable-D6UgNxuF.js","/assets/Loadable-DRmw_tjW.js","/assets/SelectField-CduE1Pbt.js","/assets/StaticTable-BFunGlsx.js","/assets/StatusChip-B8hG4lcB.js","/assets/Tabs-7lsuPoef.js","/assets/_app-CF-l7eWV.js","/assets/_app-Cs-BsC9H.js","/assets/accent-9pZLV5-s.js","/assets/account-L_z6OPoP.js","/assets/api-keys-Cl_a-iza.js","/assets/auth-jMpYxXnV.js","/assets/color-MwUzspQ2.js","/assets/index-CYGBSJJh.js","/assets/index-UkVgXYI8.css","/assets/issues-BiL0YTOS.js","/assets/issues-bNtu3C05.js","/assets/lazyRouteComponent-COc8oCnW.js","/assets/link-BFsqk5oq.js","/assets/login-BwW_yjXM.js","/assets/members-C0tiwwcG.js","/assets/members-DC6A8xav.js","/assets/ping-matrix-neDgfPe7.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-Cq_npmXz.js","/assets/servers._serverId-R6RwmyI4.js","/assets/servers.index-D-72G-NP.js","/assets/settings-DrZEvLZ6.js","/assets/ssl-CmWVwPGy.js","/assets/ssl-Dgj0dC7T.js","/assets/tooltip-CiSnpgZh.js","/assets/traffic-DZ7vtWwq.js","/assets/traffic-yG5oF3NW.js","/assets/useMatch-CPD8cSx4.js","/assets/useRefreshAll-DfCENwQZ.js","/assets/useSlot-Cjalb65z.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
