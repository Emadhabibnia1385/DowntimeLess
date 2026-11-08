import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Plugin } from "vite";

// A file the build names after its content: JS, CSS and fonts under assets/.
const HASHED = /^assets\/.+-[\w-]{8}\.(?:js|css|woff2?)$/;
const OFFLINE = "/offline.html";
const PUBLIC_FILES = ["offline.html", "manifest.webmanifest"];
const PUBLIC_FOLDERS = ["icons", "brand"];
// Live data the worker never answers: the API, the agent files and the agent description.
export const NEVER_CACHED = ["/api/", "/agent/", "/llms.txt"];

/** The worker's text: kept files from the cache, pages from the network, nothing else touched. */
export function workerSource(files: string[], version: string): string {
	return `const CACHE = "downtimeless-${version}";
const FILES = ${JSON.stringify(files)};
const NEVER = ${JSON.stringify(NEVER_CACHED)};
const OFFLINE = ${JSON.stringify(OFFLINE)};
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
`;
}

/** The files of public/ the worker keeps: offline page, manifest, icons and brand images. */
export function publicFiles(publicDir: string): string[] {
	const found = PUBLIC_FILES.filter((name) => existsSync(join(publicDir, name)));
	for (const folder of PUBLIC_FOLDERS) {
		const dir = join(publicDir, folder);
		if (existsSync(dir)) found.push(...readdirSync(dir).map((name) => `${folder}/${name}`));
	}
	return found.sort();
}

/** Emits /sw.js at build time: keeps the shell assets and public files, never data or a page. */
export function serviceWorker(): Plugin {
	let publicDir = "";
	return {
		name: "downtimeless:service-worker",
		apply: "build",
		configResolved(config) {
			publicDir = config.publicDir;
		},
		generateBundle(_, bundle) {
			const assets = Object.keys(bundle).filter((name) => HASHED.test(name));
			const statics = publicFiles(publicDir);
			const files = [...assets, ...statics].sort().map((name) => `/${name}`);
			// Hashed assets carry their version in the name; public files are hashed by content.
			const hash = createHash("sha256").update(files.join("\n"));
			for (const name of statics) hash.update(readFileSync(join(publicDir, name)));
			this.emitFile({
				type: "asset",
				fileName: "sw.js",
				source: workerSource(files, hash.digest("hex").slice(0, 10)),
			});
		},
	};
}
