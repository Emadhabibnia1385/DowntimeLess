const CACHE = "downtimeless-9411b64e9c";
const FILES = ["/assets/ChoiceFields-D2P_DA8F.js","/assets/CopyButton-BHUKJ1_o.js","/assets/DataTable-Cj2eQrwU.js","/assets/Loadable-BF0IHsab.js","/assets/SelectField-BnGhI9Wv.js","/assets/StaticTable-Dk5V0Ial.js","/assets/StatusChip-tjrTgeXM.js","/assets/Tabs-CiwdQvva.js","/assets/_app-CvF_Hhjy.js","/assets/_app-Dv-B5ZDG.js","/assets/accent-9pZLV5-s.js","/assets/account-6xXoLFFP.js","/assets/api-keys-DvaRyEWE.js","/assets/auth-_naMh7Nu.js","/assets/color-MwUzspQ2.js","/assets/index-CocF1hqG.js","/assets/index-UkVgXYI8.css","/assets/issues-CEm1Z_ke.js","/assets/issues-HPgPhhKl.js","/assets/lazyRouteComponent-CE8EeiKk.js","/assets/link-DW9H8wW9.js","/assets/login-UEl670Qg.js","/assets/members-Bqx-D-tf.js","/assets/members-DWzV8xVn.js","/assets/ping-matrix-ktuJj0KZ.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-DR-3wf75.js","/assets/servers._serverId-BZvFGsnD.js","/assets/servers.index-B3vDTmf3.js","/assets/settings-1L6tp79p.js","/assets/ssl--j7hrN3j.js","/assets/ssl-DhQtr9Ui.js","/assets/tooltip-CMMtBnzl.js","/assets/traffic-CzdNNLnC.js","/assets/traffic-yW1WG_Ga.js","/assets/useMatch-Pm0dlk4r.js","/assets/useRefreshAll-jfV0cavG.js","/assets/useSlot-B-arVTht.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
