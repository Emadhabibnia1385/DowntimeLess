const CACHE = "downtimeless-25f3c4740a";
const FILES = ["/assets/ChoiceFields-8DIxdnOr.js","/assets/CopyButton-DupsNP7w.js","/assets/DataTable-01iv1Fzi.js","/assets/Loadable-C-X3mf9v.js","/assets/Modal-_0B7q_eY.js","/assets/NumberField-DaH-VPHk.js","/assets/StaticTable-BHLghq-2.js","/assets/StatusChip-Dtkj2Dpm.js","/assets/SwitchField-CggerH6d.js","/assets/_app-C7cQxBHQ.js","/assets/_app-CW5sebL4.js","/assets/accent-9pZLV5-s.js","/assets/account-Ceu-Djad.js","/assets/api-keys-SMDgecxC.js","/assets/auth-DNkozH8t.js","/assets/color-MwUzspQ2.js","/assets/index-CZPOkKhv.css","/assets/index-MJsL1BDa.js","/assets/issues-BmRiBYg3.js","/assets/issues-DlK6Oamn.js","/assets/lazyRouteComponent-Dq7lK78r.js","/assets/link-Dtv-x9sP.js","/assets/login-BWOIVBRl.js","/assets/members-DELlUnw8.js","/assets/members-w3EEWW9V.js","/assets/panel-CDrL9z62.js","/assets/panel-VGREgmwJ.js","/assets/ping-matrix-CjMzuMHT.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-BmukZRGQ.js","/assets/servers._serverId-Dun0Ef6W.js","/assets/servers.index-BdX15kRq.js","/assets/settings-YwggpMwQ.js","/assets/ssl-B63NGKnI.js","/assets/ssl-q4LZ8npS.js","/assets/tooltip-C1d-wkKa.js","/assets/traffic-BdrSfRTn.js","/assets/traffic-mlHqrzCG.js","/assets/useMatch-CDPRtRyG.js","/assets/useRefreshAll-9qcE8WkB.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
