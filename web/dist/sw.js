const CACHE = "downtimeless-4d9a9aadfb";
const FILES = ["/assets/ChoiceFields-D9ZkzLCi.js","/assets/CopyButton-Bb4P4nBs.js","/assets/DataTable-BvDTsSby.js","/assets/Loadable-CqCZn1cJ.js","/assets/Modal-CTVfK8XW.js","/assets/NumberField-Cqaqvwdw.js","/assets/SelectField-pldR1WM_.js","/assets/StaticTable-CxeUcCkF.js","/assets/StatusChip-CI9qFugB.js","/assets/_app-CS9Wl8Tl.js","/assets/_app-CrLOKXx5.js","/assets/accent-9pZLV5-s.js","/assets/account-BP3_WXDK.js","/assets/api-keys-CsaCSFUA.js","/assets/auth-B5PZd0E3.js","/assets/color-MwUzspQ2.js","/assets/index-NiQOpyLF.js","/assets/index-wScpMy1N.css","/assets/issues-5hd80P_V.js","/assets/issues-C2YxyNEz.js","/assets/lazyRouteComponent-CeBFPXgm.js","/assets/link-DcaTeHdV.js","/assets/login-QuBx_jHI.js","/assets/members-1PLdkV38.js","/assets/members-CF2omtFU.js","/assets/panel-BL34s7kk.js","/assets/panel-aDwsUTZD.js","/assets/ping-matrix-B9JcNylS.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BSCVNrLP.js","/assets/servers._serverId-bL5bIMS3.js","/assets/servers.index-B6GaWV1P.js","/assets/settings-CRdplhpW.js","/assets/ssl-CB5lpaT9.js","/assets/ssl-DtHJpMZp.js","/assets/tooltip-B5DMhLsP.js","/assets/traffic-RRaQLCY-.js","/assets/traffic-eHIYLO_r.js","/assets/useMatch-DolLjbnV.js","/assets/useRefreshAll-CNsu54Sr.js","/assets/useSlot-DuVFs8PH.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
