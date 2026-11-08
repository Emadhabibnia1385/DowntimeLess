const CACHE = "downtimeless-3bfcec53f1";
const FILES = ["/assets/ChoiceFields-BL6TAcy-.js","/assets/CopyButton-jjjS7oYQ.js","/assets/DataTable-DeuWSIva.js","/assets/Loadable-CHbasTH6.js","/assets/SelectField-WJoyfPZF.js","/assets/StaticTable-6ciy5bUx.js","/assets/StatusChip-DkWSbVMv.js","/assets/_app-DSTACDwV.js","/assets/_app-Z8vDTiEA.js","/assets/accent-9pZLV5-s.js","/assets/account-C3XKMnGN.js","/assets/api-keys-B9pD6UXQ.js","/assets/auth-CcDU96ib.js","/assets/color-MwUzspQ2.js","/assets/index-BakDV44d.js","/assets/index-wpPw66NR.css","/assets/issues-DyFkd0gQ.js","/assets/issues-igz3-xfJ.js","/assets/lazyRouteComponent-C2IzRVqg.js","/assets/link-Cmo3qXSW.js","/assets/login-DpjKLs7a.js","/assets/members-C86uByo4.js","/assets/members-D06jOJEs.js","/assets/ping-matrix-QCCaUXqP.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-GmRL6Y2G.js","/assets/servers._serverId-LOiHXBZ5.js","/assets/servers.index-CQ5kt3g9.js","/assets/settings-Ba_x3C0z.js","/assets/ssl-CIOqHrNK.js","/assets/ssl-D4NfSmIa.js","/assets/tooltip-DcC3cuDy.js","/assets/traffic-CW5j2y1H.js","/assets/traffic-DePxRWfB.js","/assets/useMatch-BVS31vfT.js","/assets/useRefreshAll-_YCGXuxR.js","/assets/useSlot-_hbDmzGR.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
