const CACHE = "downtimeless-aed693bafb";
const FILES = ["/assets/DataTable-SMj3qhV9.js","/assets/KeyValueList-9OMUmfmW.js","/assets/Loadable-C_ennV8h.js","/assets/Modal-DdMQrl_x.js","/assets/NumberField-BVeoeVMH.js","/assets/PageHeader-C8VMqSka.js","/assets/SectionCard-4KqAiJkg.js","/assets/StatCard-CRbLEl53.js","/assets/StatusChip-CTlDYrww.js","/assets/_app-BPSJttAE.js","/assets/_app-D5-3h_Hu.js","/assets/accent-9pZLV5-s.js","/assets/account-d0cmGS7u.js","/assets/api-keys-CR_slMhu.js","/assets/auth-kiXuRb7R.js","/assets/color-MwUzspQ2.js","/assets/index--GD_ewrB.js","/assets/index-DhIU9AVV.css","/assets/issues-CHremGZF.js","/assets/issues-CoCC0SfZ.js","/assets/lazyRouteComponent-CvRYR6p7.js","/assets/link-DOmaO236.js","/assets/login-wVBdBBll.js","/assets/overview-Dz4DHeVU.js","/assets/ping-matrix-DOR4X2ad.js","/assets/radio-group-CITs_meb.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-DHmEcABn.js","/assets/servers._serverId-DgktO3E4.js","/assets/servers.index-VUjr6qeh.js","/assets/settings-Ck2xYg-B.js","/assets/settings-avZvokay.js","/assets/ssl-B7jwo6ar.js","/assets/ssl-CSxPMQA3.js","/assets/table.styles-DIsu5Y-B.js","/assets/tooltip-PFT76iMS.js","/assets/useDocumentTitle-CDA3UqHm.js","/assets/useLocalizedStringFormatter-CYKhyFLx.js","/assets/useMatch-B5Ir4HwX.js","/assets/useRefreshAll-2RUkeZ3b.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
