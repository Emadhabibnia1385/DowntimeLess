const CACHE = "downtimeless-d9906ef102";
const FILES = ["/assets/ChoiceFields-rYRBW8ry.js","/assets/CopyButton-3uBMJ9QR.js","/assets/DataTable-CCRqvtSi.js","/assets/Loadable-D95ipQaC.js","/assets/Modal-DAjovfKR.js","/assets/NumberField-CWQCny7G.js","/assets/StaticTable-OJrP2pm4.js","/assets/StatusChip-DmLDHQmi.js","/assets/SwitchField-BJ7fKUAc.js","/assets/_app-Bk4sqQK-.js","/assets/_app-tB3G09xE.js","/assets/accent-9pZLV5-s.js","/assets/account-CBkekX-l.js","/assets/api-keys-CVsp6UK2.js","/assets/auth-DJlAecTJ.js","/assets/color-MwUzspQ2.js","/assets/index-CZPOkKhv.css","/assets/index-DsnLlSxd.js","/assets/issues-CaTIg7C9.js","/assets/issues-CkjwWRz8.js","/assets/lazyRouteComponent-Cu-U6H_i.js","/assets/link-D4RKdMC7.js","/assets/login-DodAVPGl.js","/assets/members-CFitMUFb.js","/assets/members-COVu5HHV.js","/assets/panel-Bi1NDXzh.js","/assets/panel-BjpQHKZD.js","/assets/ping-matrix-DJXQxaQs.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BrepWN9f.js","/assets/servers._serverId-ywuBZCXt.js","/assets/servers.index-CnhsetB6.js","/assets/settings-BSCEWhX2.js","/assets/ssl-CM55hBKW.js","/assets/ssl-OhQmEoXN.js","/assets/tooltip-DsTygkpE.js","/assets/traffic-BoqKBgeX.js","/assets/traffic-CGOKcHHw.js","/assets/useMatch-BVe66a6h.js","/assets/useRefreshAll-DYCsF5qH.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
