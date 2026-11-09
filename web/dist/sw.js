const CACHE = "downtimeless-4727742a0e";
const FILES = ["/assets/ChoiceFields-wcKyuNdf.js","/assets/CopyButton-CwMk5mbr.js","/assets/DataTable-DTdB24AD.js","/assets/Loadable-CClaY8NI.js","/assets/Modal-3UY_iQXo.js","/assets/NumberField-CYvnNNCO.js","/assets/StaticTable-DCzrTLUR.js","/assets/StatusChip-DvOAbdpQ.js","/assets/SwitchField-PS02Fkdu.js","/assets/_app-BAJC3Crz.js","/assets/_app-HBz5rT16.js","/assets/accent-9pZLV5-s.js","/assets/account-CHT1Ro6v.js","/assets/api-keys-DzbXL9Nh.js","/assets/auth-BRr0yPqj.js","/assets/color-MwUzspQ2.js","/assets/index-CZPOkKhv.css","/assets/index-CxZSyWSK.js","/assets/issues-Cb7S6OqG.js","/assets/issues-DbmbQjBW.js","/assets/lazyRouteComponent-BJBJ_ral.js","/assets/link-BlUEIAKR.js","/assets/login-C54b2GKV.js","/assets/members-BYESorXK.js","/assets/members-CU9EeFWc.js","/assets/panel--5WLtDdH.js","/assets/panel-CienXLVP.js","/assets/ping-matrix-DWbeyzg2.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-f4Bt2zdE.js","/assets/servers._serverId-ByGTMc4s.js","/assets/servers.index-CRIZzWnX.js","/assets/settings-DvM1SbgU.js","/assets/ssl-B6JGI_Ye.js","/assets/ssl-BcWFdgzL.js","/assets/tooltip-CylR4OzF.js","/assets/traffic-CwtKFf97.js","/assets/traffic-DSYCPxs-.js","/assets/useMatch-C-00qaHA.js","/assets/useRefreshAll-BKrj8TtU.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
