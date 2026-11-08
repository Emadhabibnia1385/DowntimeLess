const CACHE = "downtimeless-49c00f4cae";
const FILES = ["/assets/CollectionBuilder-fbKqgVna.js","/assets/ConfirmDialog-CfUD3tIa.js","/assets/CopyButton-DW8AUjSV.js","/assets/DataTable-O-hIX9XH.js","/assets/KeyValueList-D-H9sk6j.js","/assets/Loadable-d5LOOJmP.js","/assets/Modal-Dbr9M4pp.js","/assets/NumberField-7lWhKjgV.js","/assets/StaticTable-C_8iZ54i.js","/assets/StatusChip-Dst3apbx.js","/assets/_app-DVr7c7g4.js","/assets/_app-I5tFFfJb.js","/assets/accent-9pZLV5-s.js","/assets/account-B7m7EFG8.js","/assets/api-keys-kvX9smY6.js","/assets/auth-DA8ToO0a.js","/assets/color-MwUzspQ2.js","/assets/index-D4quCN62.css","/assets/index-maMx6tOi.js","/assets/issues-BNwKLHrF.js","/assets/issues-_Iy07d5b.js","/assets/lazyRouteComponent-GJPsGRqL.js","/assets/link-BLIHUa2h.js","/assets/login-D00HSzVU.js","/assets/number-DLVba5xe.js","/assets/overview-k_ZXlZMc.js","/assets/ping-matrix-lij1lGj7.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-9BTxXGOg.js","/assets/servers._serverId-Caa4XI-B.js","/assets/servers.index-B0YXup1n.js","/assets/settings-CFOaCcTq.js","/assets/ssl-CqjH-xs9.js","/assets/ssl-CzsaUDnB.js","/assets/tooltip-DKm50H91.js","/assets/useDocumentTitle-Bjd1QAaj.js","/assets/useLoadMoreSentinel-B_zIV2kP.js","/assets/useMatch-DtvAqFVl.js","/assets/useRefreshAll-HNCrHP8h.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
