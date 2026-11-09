const CACHE = "downtimeless-a60b90ec40";
const FILES = ["/assets/ChoiceFields-BjepHWDr.js","/assets/CopyButton-PaxaiwFA.js","/assets/DataTable-DQjuGP1D.js","/assets/Loadable-2-vN2GkF.js","/assets/Modal-64waY7iT.js","/assets/NumberField-BOwbx0gn.js","/assets/StaticTable-CDWovvZz.js","/assets/StatusChip-Bi_lhaGi.js","/assets/SwitchField-BhPQ2Fy-.js","/assets/_app-C57M7DGL.js","/assets/_app-DL8Vwe1k.js","/assets/accent-9pZLV5-s.js","/assets/account-Bg6ejsEf.js","/assets/api-keys-_fhtk8ew.js","/assets/auth-D6HLc2BI.js","/assets/color-MwUzspQ2.js","/assets/index-C3bEm_3f.js","/assets/index-DB0zNNXj.css","/assets/issues-BTqs2TWN.js","/assets/issues-BjMK9q7D.js","/assets/lazyRouteComponent-DYaUrAdV.js","/assets/link-DBdfObW2.js","/assets/login-CjPI7K9r.js","/assets/members-C3IEOiQL.js","/assets/members-DP-oflLn.js","/assets/panel-Cx5LSiXa.js","/assets/panel-xBf_VnMv.js","/assets/ping-matrix-Dg98xSgI.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-DfC94Hk1.js","/assets/servers._serverId-D5cwLZKn.js","/assets/servers.index-CEkEntav.js","/assets/settings-BJiQa0os.js","/assets/ssl-BbhK-BMk.js","/assets/ssl-D7HsZvPe.js","/assets/tooltip-BGx31yTw.js","/assets/traffic-CwvlFfCt.js","/assets/traffic-jAhura6a.js","/assets/useMatch-C0HPYyMC.js","/assets/useRefreshAll-DZVRje0h.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
