const CACHE = "downtimeless-3b87fd4c33";
const FILES = ["/assets/DataTable-Bs-4TiFZ.js","/assets/KeyValueList-B1_IbNmJ.js","/assets/Loadable-BagAkott.js","/assets/Modal-C7YKrieM.js","/assets/NumberField-rSYc-mgm.js","/assets/PageHeader-BJceKWuu.js","/assets/SectionCard-OAsPliSn.js","/assets/StatCard-QWwIFvw6.js","/assets/StatusChip-onbKEjXT.js","/assets/_app-MC4ovpNW.js","/assets/_app-aAib4lEm.js","/assets/accent-9pZLV5-s.js","/assets/account-B93LeEo4.js","/assets/api-keys-CY3PeL6v.js","/assets/auth-DNJYn1-3.js","/assets/color-MwUzspQ2.js","/assets/index-B-9efVAt.js","/assets/index-COqUxoYW.css","/assets/issues-C_hsu0Xt.js","/assets/issues-Thtq2Oss.js","/assets/lazyRouteComponent-NNwpD5Vi.js","/assets/link-CoKtT-hD.js","/assets/login-mVpAyhQx.js","/assets/overview-DnC_7GK1.js","/assets/ping-matrix-D5Y4vYyi.js","/assets/radio-group-C6eqMOvd.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-CfAHW0aB.js","/assets/servers._serverId-c_vfEj3x.js","/assets/servers.index-DPZrk5HI.js","/assets/settings-C8SNoSL6.js","/assets/settings-ChLj-dn-.js","/assets/ssl-BuA5VpAI.js","/assets/ssl-CYiW4ION.js","/assets/table.styles-CdBxuawz.js","/assets/tooltip-CXrSnt7Y.js","/assets/useDocumentTitle-BXZBC1Wy.js","/assets/useLocalizedStringFormatter-dSFz1GeB.js","/assets/useMatch-xCgEBEEy.js","/assets/useRefreshAll-BU4eJ2F8.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
