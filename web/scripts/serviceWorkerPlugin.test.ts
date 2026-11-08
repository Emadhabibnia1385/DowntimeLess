import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { publicFiles, serviceWorker, workerSource } from "./serviceWorkerPlugin.ts";

const FILES = ["/assets/index-AbCd1234.js", "/assets/index-EfGh5678.css", "/offline.html"];
const ORIGIN = "https://panel.example";

type Listener = (event: Record<string, unknown>) => void;

// Runs the worker's text against a small stand-in for a worker's globals.
function boot(version = "v1", { online = true } = {}) {
	const listeners: Record<string, Listener> = {};
	const caches = new Map<string, Set<string>>([
		["downtimeless-old", new Set()],
		["other-app", new Set()],
	]);
	const asked: string[] = [];
	const globals = {
		self: {
			addEventListener: (type: string, listener: Listener) => {
				listeners[type] = listener;
			},
			skipWaiting: vi.fn(),
			clients: { claim: vi.fn() },
		},
		caches: {
			open: async (name: string) => {
				const store = caches.get(name) ?? new Set<string>();
				caches.set(name, store);
				return {
					addAll: async (urls: string[]) => urls.forEach((url) => store.add(url)),
					match: async (request: string | { url: string }) => {
						const url = typeof request === "string" ? request : request.url;
						return store.has(new URL(url, ORIGIN).pathname) ? `cached ${url}` : undefined;
					},
				};
			},
			keys: async () => [...caches.keys()],
			delete: async (name: string) => caches.delete(name),
		},
		location: { origin: ORIGIN },
		fetch: async (request: { url: string }) => {
			asked.push(request.url);
			if (!online) throw new TypeError("network down");
			return `network ${request.url}`;
		},
		URL,
	};
	new Function(...Object.keys(globals), workerSource(FILES, version))(...Object.values(globals));
	return { listeners, caches, asked, globals };
}

async function fetched(listeners: Record<string, Listener>, request: Record<string, unknown>) {
	let answer: Promise<unknown> | undefined;
	listeners.fetch?.({ request, respondWith: (promise: Promise<unknown>) => (answer = promise) });
	return answer && (await answer);
}

describe("the worker", () => {
	it("keeps the shell files on install and takes over at once", async () => {
		const { listeners, caches, globals } = boot("v1");
		let done: Promise<unknown> | undefined;
		listeners.install?.({ waitUntil: (promise: Promise<unknown>) => (done = promise) });
		await done;
		expect([...(caches.get("downtimeless-v1") ?? [])]).toEqual(FILES);
		expect(globals.self.skipWaiting).toHaveBeenCalledOnce();
	});

	it("drops its own older caches on activate, and no one else's", async () => {
		const { listeners, caches, globals } = boot("v2");
		caches.set("downtimeless-v2", new Set(FILES));
		let done: Promise<unknown> | undefined;
		listeners.activate?.({ waitUntil: (promise: Promise<unknown>) => (done = promise) });
		await done;
		expect([...caches.keys()].sort()).toEqual(["downtimeless-v2", "other-app"]);
		expect(globals.self.clients.claim).toHaveBeenCalledOnce();
	});

	it("answers a kept file from the cache, and asks the network for one not kept yet", async () => {
		const { listeners, caches, asked } = boot("v1");
		caches.set("downtimeless-v1", new Set([FILES[0] as string]));
		const kept = { url: `${ORIGIN}${FILES[0]}`, method: "GET", mode: "cors" };
		expect(await fetched(listeners, kept)).toBe(`cached ${kept.url}`);
		expect(asked).toEqual([]);
		const late = { url: `${ORIGIN}${FILES[1]}`, method: "GET", mode: "cors" };
		expect(await fetched(listeners, late)).toBe(`network ${late.url}`);
	});

	it("serves a page from the network first, and the offline page only when the network is down", async () => {
		const page = { url: `${ORIGIN}/servers`, method: "GET", mode: "navigate" };
		const online = boot("v1");
		online.caches.set("downtimeless-v1", new Set(FILES));
		expect(await fetched(online.listeners, page)).toBe(`network ${page.url}`);
		const down = boot("v1", { online: false });
		down.caches.set("downtimeless-v1", new Set(FILES));
		expect(await fetched(down.listeners, page)).toBe("cached /offline.html");
	});

	it("never touches the API, the agent files, llms.txt, a write, another site or an unkept file", async () => {
		const { listeners, caches } = boot("v1", { online: false });
		caches.set(
			"downtimeless-v1",
			new Set([...FILES, "/api/v1/servers", "/llms.txt", "/agent/agent.py"]),
		);
		const requests = [
			{ url: `${ORIGIN}/api/v1/servers`, method: "GET", mode: "cors" },
			{ url: `${ORIGIN}/api/docs`, method: "GET", mode: "navigate" },
			{ url: `${ORIGIN}/agent/install.sh`, method: "GET", mode: "navigate" },
			{ url: `${ORIGIN}/agent/agent.py`, method: "GET", mode: "cors" },
			{ url: `${ORIGIN}/llms.txt`, method: "GET", mode: "navigate" },
			{ url: `${ORIGIN}${FILES[0]}`, method: "POST", mode: "cors" },
			{ url: `https://other.example${FILES[0]}`, method: "GET", mode: "cors" },
			{ url: `${ORIGIN}/fonts/webfonts/Vazirmatn.woff2`, method: "GET", mode: "cors" },
		];
		for (const request of requests) expect(await fetched(listeners, request)).toBeUndefined();
	});
});

describe("the plugin", () => {
	type Hooks = {
		configResolved: (config: { publicDir: string }) => void;
		generateBundle: (
			this: { emitFile: (file: unknown) => void },
			options: unknown,
			bundle: object,
		) => void;
	};

	function publicDir() {
		const dir = mkdtempSync(join(tmpdir(), "dl-public-"));
		mkdirSync(join(dir, "icons"));
		mkdirSync(join(dir, "brand"));
		mkdirSync(join(dir, "fonts"));
		writeFileSync(join(dir, "offline.html"), "<p>offline</p>");
		writeFileSync(join(dir, "manifest.webmanifest"), "{}");
		writeFileSync(join(dir, "icons", "icon-192.png"), "a");
		writeFileSync(join(dir, "brand", "logo-dark.webp"), "b");
		writeFileSync(join(dir, "fonts", "big.woff2"), "c");
		return dir;
	}

	function emit(dir: string, names: string[]) {
		const emitted: { fileName: string; source: string }[] = [];
		const hooks = serviceWorker() as unknown as Hooks;
		hooks.configResolved({ publicDir: dir });
		hooks.generateBundle.call(
			{ emitFile: (file) => emitted.push(file as { fileName: string; source: string }) },
			{},
			Object.fromEntries(names.map((name) => [name, {}])),
		);
		return emitted;
	}

	it("lists the offline page, manifest, icons and brand images of public/", () => {
		expect(publicFiles(publicDir())).toEqual([
			"brand/logo-dark.webp",
			"icons/icon-192.png",
			"manifest.webmanifest",
			"offline.html",
		]);
	});

	it("emits /sw.js listing the hashed assets and those public files, and no page or data", () => {
		const [file, ...rest] = emit(publicDir(), [
			"index.html",
			"assets/index-AbCd1234.js",
			"assets/index-EfGh5678.css",
			"assets/Vazirmatn-QrSt1234.woff2",
			"assets/unhashed.js",
		]);
		expect(rest).toEqual([]);
		expect(file?.fileName).toBe("sw.js");
		const source = file?.source ?? "";
		for (const kept of [
			"/assets/index-AbCd1234.js",
			"/assets/index-EfGh5678.css",
			"/assets/Vazirmatn-QrSt1234.woff2",
			"/offline.html",
			"/manifest.webmanifest",
			"/icons/icon-192.png",
			"/brand/logo-dark.webp",
		])
			expect(source).toContain(`"${kept}"`);
		for (const left of ["/index.html", "/assets/unhashed.js", "/fonts/big.woff2"])
			expect(source).not.toContain(`"${left}"`);
	});

	it("changes the cache name when a public file changes, so an icon swap reaches installed apps", () => {
		const dir = publicDir();
		const name = () =>
			/downtimeless-(\w+)/.exec(emit(dir, ["assets/a-AbCd1234.js"])[0]?.source ?? "")?.[1];
		const before = name();
		writeFileSync(join(dir, "icons", "icon-192.png"), "changed");
		expect(name()).not.toBe(before);
	});
});
