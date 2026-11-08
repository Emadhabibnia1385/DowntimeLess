const CACHE = "downtimeless-2b5d88d721";
const FILES = ["/assets/CollectionBuilder-nnqe7fQx.js","/assets/ConfirmDialog-DzICgXHZ.js","/assets/DataTable-C9PVC_ZR.js","/assets/IpText-BOtUIVDp.js","/assets/KeyValueList-7k9sV-SV.js","/assets/Loadable-kF-u1qpt.js","/assets/Modal-DsLXxDhc.js","/assets/NumberField-BeANd58h.js","/assets/PageHeader-DeVC1QXG.js","/assets/SectionCard-CFJ9WVfb.js","/assets/StatusChip-BAdfXTB3.js","/assets/_app-9UVWmIN3.js","/assets/_app-m7ZRoVXC.js","/assets/accent-9pZLV5-s.js","/assets/account-C10Leucz.js","/assets/api-keys-DlCWPTZR.js","/assets/auth-byeQ3J2o.js","/assets/color-MwUzspQ2.js","/assets/index-DlStfU7I.js","/assets/index-tJvLFFsr.css","/assets/issues-CbS3WTDN.js","/assets/issues-LRlVtc59.js","/assets/lazyRouteComponent-DY6Q3x7A.js","/assets/link-gO-tt1ce.js","/assets/login-BW5biv_K.js","/assets/number-D6xxqgMK.js","/assets/overview-Ju259hiI.js","/assets/ping-matrix-3RMjzr7Q.js","/assets/radio-group-CBzXDYQ-.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BAnyy_-n.js","/assets/servers-CIxb-55l.js","/assets/servers._serverId-MsKwXtU8.js","/assets/servers.index-CQ-ne80c.js","/assets/settings-CnozzPwX.js","/assets/settings-vO7nDFRa.js","/assets/ssl-CUW9RvCb.js","/assets/ssl-D3O3wQGK.js","/assets/tooltip-B7lUkb17.js","/assets/useDocumentTitle-DGrRXRYf.js","/assets/useEvent-ZYIkSUP4.js","/assets/useLocalizedStringFormatter-CBHbOV0c.js","/assets/useMatch-DLnSNIdc.js","/assets/useRefreshAll-C2Dpc6g4.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
