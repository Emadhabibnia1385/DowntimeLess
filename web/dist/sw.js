const CACHE = "downtimeless-e632a4f387";
const FILES = ["/assets/DataTable-CEA9qeT2.js","/assets/KeyValueList-B7M5m0zH.js","/assets/Loadable-DDmM6H6n.js","/assets/Modal-D8Q-v_Oy.js","/assets/NumberField-BNVNY6_g.js","/assets/PageHeader-BA4pMB53.js","/assets/SectionCard-D0KzKZ1p.js","/assets/StatCard-vFH_bFfx.js","/assets/StatusChip-BP-cnArZ.js","/assets/_app-BcdPuJgq.js","/assets/_app-RAQyfNzr.js","/assets/accent-9pZLV5-s.js","/assets/account-DNqI3MO6.js","/assets/api-keys-BvX1WJ0T.js","/assets/auth-CvkL0Tzk.js","/assets/color-MwUzspQ2.js","/assets/index-B88kItD0.js","/assets/index-CL3vx2lO.css","/assets/issues-BiZV3Qy-.js","/assets/issues-DwoP_Gc6.js","/assets/lazyRouteComponent-DKuIdw3E.js","/assets/link-Dgg0fqXb.js","/assets/login-B8Zb_vHc.js","/assets/overview-kDnAbBYZ.js","/assets/ping-matrix-DIoE4U-8.js","/assets/radio-group-CiIcXE3W.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BrlmhMIp.js","/assets/servers._serverId-DGV1PgHO.js","/assets/servers.index-BboAB7JY.js","/assets/settings-CPCwJS53.js","/assets/settings-DQX94rcS.js","/assets/ssl-CFcfBbig.js","/assets/ssl-cbXljTLL.js","/assets/table.styles-_oWffXyQ.js","/assets/useDocumentTitle-BBBYptiI.js","/assets/useLocalizedStringFormatter--es3-GR3.js","/assets/useMatch-C-MsgFfH.js","/assets/useRefreshAll-eoHlSjtz.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
