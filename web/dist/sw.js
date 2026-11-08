const CACHE = "downtimeless-7454e86c65";
const FILES = ["/assets/ChoiceFields-CNTXCn48.js","/assets/CopyButton-BaxKiZ9t.js","/assets/DataTable-BcHwCl41.js","/assets/Loadable-B8zsWUmv.js","/assets/Modal-EfmdXvDW.js","/assets/NumberField-m2q10vQn.js","/assets/SelectField-CRO0pnV2.js","/assets/StaticTable-O_f9DJGx.js","/assets/StatusChip-B6Gz8VRP.js","/assets/_app-B69jw4jR.js","/assets/_app-CUB1pO-e.js","/assets/accent-9pZLV5-s.js","/assets/account-_sqmte7Q.js","/assets/api-keys-QlHAprUA.js","/assets/auth-BkhTqhkx.js","/assets/color-MwUzspQ2.js","/assets/index-BIEaq2Sv.css","/assets/index-DN1vqcin.js","/assets/issues-DF8nY1aq.js","/assets/issues-DXIwlF6w.js","/assets/lazyRouteComponent-CmIIOtzV.js","/assets/link-p3sJbNvp.js","/assets/login-DN4mNjZi.js","/assets/members-8c_MEoF-.js","/assets/members-BJqtTlUZ.js","/assets/panel-BjhOnoCY.js","/assets/panel-nF9xPB3e.js","/assets/ping-matrix-Du0TsaQo.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-DWYj428Z.js","/assets/servers._serverId-CYR7YHmw.js","/assets/servers.index-BHG5XqJc.js","/assets/settings-XE_Te73S.js","/assets/ssl-BQzGG9Jn.js","/assets/ssl-PUig2giH.js","/assets/tooltip-CLaFsSLs.js","/assets/traffic-DFGjL4wn.js","/assets/traffic-cQUbqk_v.js","/assets/useMatch-BvoJuaJA.js","/assets/useRefreshAll-C7tZFVpo.js","/assets/useSlot-DMxQ4x4i.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
