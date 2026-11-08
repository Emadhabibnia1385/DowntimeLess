const CACHE = "downtimeless-81acb0e324";
const FILES = ["/assets/CollectionBuilder-ENuvBC8d.js","/assets/ConfirmDialog-C0pz9xO9.js","/assets/CopyButton-Chosgp9P.js","/assets/DataTable-CQdWNK8q.js","/assets/IpText-D243Nxmq.js","/assets/KeyValueList-DCR18nwN.js","/assets/Loadable-CEVHLiVm.js","/assets/Modal-DuT3KDLJ.js","/assets/NumberField-B3nKDkP6.js","/assets/PageHeader-DSV3soGK.js","/assets/SectionCard-CvymF46A.js","/assets/StatusChip-BXQME2my.js","/assets/_app-BOQK4Igi.js","/assets/_app-Dqpvifrj.js","/assets/accent-9pZLV5-s.js","/assets/account-CDWC43uu.js","/assets/api-keys-ChJgh1LY.js","/assets/auth-DEo1ESzK.js","/assets/color-MwUzspQ2.js","/assets/index-CucYAoHm.js","/assets/index-tJvLFFsr.css","/assets/issues-Cv9k-3N0.js","/assets/issues-Dat0nRX2.js","/assets/lazyRouteComponent-Djj9EcTI.js","/assets/link-DNu9xVGj.js","/assets/login-Bi5M53ib.js","/assets/number-D6xxqgMK.js","/assets/overview-1VAoF7Sx.js","/assets/ping-matrix-DoxG99qi.js","/assets/radio-group-CENs_GAd.js","/assets/rolldown-runtime-WkwZ5CU-.js","/assets/servers-D-A6e62D.js","/assets/servers-DzCeP_2P.js","/assets/servers._serverId-oFy3h1h7.js","/assets/servers.index-CjVnuYFM.js","/assets/settings-B3NVnQuK.js","/assets/settings-CpQYuZWi.js","/assets/ssl-B4Xm5mSQ.js","/assets/ssl-C9eLoOG3.js","/assets/tooltip-C4ZoD8gZ.js","/assets/useDocumentTitle-DeB9ZPCl.js","/assets/useEvent-DKT3XtdX.js","/assets/useLocalizedStringFormatter-DlKi7BvV.js","/assets/useMatch-TD99G4e5.js","/assets/useRefreshAll-DhNtEpEc.js","/brand/icon-dark.png","/brand/icon-light.png","/brand/logo-dark.webp","/brand/logo-light.webp","/icons/apple-touch-icon.png","/icons/favicon-32.png","/icons/favicon-48.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-192.png","/icons/maskable-512.png","/manifest.webmanifest","/offline.html"];
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
