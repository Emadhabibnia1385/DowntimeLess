const CACHE = "downtimeless-3f4744d344";
const FILES = ["/assets/ChoiceFields-BuTx8ZCZ.js","/assets/CopyButton-dIjIXX2n.js","/assets/DataTable-C3tP4x5Q.js","/assets/Loadable-DlIEjdqX.js","/assets/Modal-CdswuQfT.js","/assets/NumberField-ZCDJB1rb.js","/assets/SelectField-BkdhLDFA.js","/assets/StaticTable-DOzB6WEk.js","/assets/StatusChip-BQzBmQ1c.js","/assets/_app-BtUC8TCF.js","/assets/_app-DbQHNJPM.js","/assets/accent-9pZLV5-s.js","/assets/account-CKStkosd.js","/assets/api-keys-yG0lQXxe.js","/assets/auth-Q-5kzSOi.js","/assets/color-MwUzspQ2.js","/assets/index-DxqZCTE6.js","/assets/index-wScpMy1N.css","/assets/issues-CAMZXuJI.js","/assets/issues-DhrtNoQ_.js","/assets/lazyRouteComponent-DmRGaXgd.js","/assets/link-C2FSDEeh.js","/assets/login-BdPhWfeI.js","/assets/members-Cks-Ycut.js","/assets/members-CrmdDRZL.js","/assets/panel-BD6s8mGi.js","/assets/panel-BZC5e0Ej.js","/assets/ping-matrix-nDGGNYSs.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BcRqCV7b.js","/assets/servers._serverId-DCicxdud.js","/assets/servers.index-BOMes91U.js","/assets/settings-DwJ7Hyfu.js","/assets/ssl-B6MRknWC.js","/assets/ssl-QLRJTELI.js","/assets/tooltip-CQHKfzDR.js","/assets/traffic-D6otvuWj.js","/assets/traffic-DRZvozer.js","/assets/useMatch-OXq5kx_D.js","/assets/useRefreshAll-B9EMGcgP.js","/assets/useSlot-VCML1MrY.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
