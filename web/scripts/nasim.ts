// `nasim:sync <nyxon checkout>` copies @nyxon/nasim from NYXON; `check:nasim` proves the copy.
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";

const ROOT = join(import.meta.dirname, "..");
const VENDOR = join(ROOT, "vendor/nasim");
const LOCK = join(ROOT, "vendor/nasim.lock.json");
const UPSTREAM_PATH = "libs/nasim";
const COPIED = ["src", "README.md", "CHANGELOG.md"];
const MANIFEST_KEYS = [
	"name",
	"version",
	"private",
	"type",
	"sideEffects",
	"exports",
	"dependencies",
	"peerDependencies",
];
// One copy of each, or the date picker loses the Persian locale (Nasim README «Setup»).
const SHARED_OVERRIDES = ["react-aria", "react-aria-components", "react-stately"];

type Json = Record<string, unknown>;
type Deps = Record<string, string>;
type Entry = { path: string; bytes: Buffer };
type Lock = {
	package: string;
	version: string;
	repository: string;
	path: string;
	commit: string;
	overrides: Deps;
	sha256: string;
};

/** The package.json an importer needs: the library's scripts and test tooling stay in NYXON. */
export function vendoredManifest(upstream: Json): Json {
	return Object.fromEntries(
		MANIFEST_KEYS.filter((key) => key in upstream).map((key) => [key, upstream[key]]),
	);
}

export function treeHash(entries: Entry[]): string {
	const hash = createHash("sha256");
	for (const { path, bytes } of [...entries].sort((a, b) => (a.path < b.path ? -1 : 1))) {
		hash.update(`${path}\0${bytes.length}\0`).update(bytes);
	}
	return hash.digest("hex");
}

/** Every package both pin where the versions differ: two copies of a library break its context. */
export function pinDrift(nasim: Deps, app: Deps): string[] {
	return Object.entries(nasim)
		.filter(([name, version]) => name in app && app[name] !== version)
		.map(([name, version]) => `${name}: the app has ${app[name]}, Nasim ${version}`);
}

const readJson = (file: string): Json => JSON.parse(readFileSync(file, "utf8"));

function walk(base: string, folder = base): Entry[] {
	return readdirSync(folder, { withFileTypes: true }).flatMap((item) => {
		const full = join(folder, item.name);
		if (item.isDirectory()) return walk(base, full);
		return [{ path: relative(base, full).split(sep).join("/"), bytes: readFileSync(full) }];
	});
}

function upstreamEntries(library: string): Entry[] {
	const files = COPIED.flatMap((name) =>
		name.includes(".")
			? [{ path: name, bytes: readFileSync(join(library, name)) }]
			: walk(library, join(library, name)),
	);
	const manifest = vendoredManifest(readJson(join(library, "package.json")));
	return [
		...files,
		{ path: "package.json", bytes: Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`) },
	];
}

function appProblems(lock: Lock): string[] {
	const app = readJson(join(ROOT, "package.json"));
	const pins = { ...(app.dependencies as Deps), ...(app.devDependencies as Deps) };
	const nasim = readJson(join(VENDOR, "package.json")).dependencies as Deps;
	const overrides = (app.overrides ?? {}) as Deps;
	const missing = Object.entries(lock.overrides)
		.filter(([name, version]) => overrides[name] !== version)
		.map(
			([name, version]) => `overrides.${name} must be ${version}, as in NYXON's root package.json`,
		);
	return [...pinDrift(nasim, pins), ...missing];
}

function sync(checkout: string) {
	const git = (...args: string[]) =>
		execFileSync("git", ["-C", checkout, ...args], { encoding: "utf8" }).trim();
	if (git("status", "--porcelain", "--", UPSTREAM_PATH, "package.json")) {
		throw new Error(
			`${checkout} has uncommitted changes in ${UPSTREAM_PATH}: commit them in NYXON first`,
		);
	}
	const entries = upstreamEntries(join(checkout, UPSTREAM_PATH));
	rmSync(VENDOR, { recursive: true, force: true });
	for (const { path, bytes } of entries) {
		mkdirSync(dirname(join(VENDOR, path)), { recursive: true });
		writeFileSync(join(VENDOR, path), bytes);
	}
	const root = readJson(join(checkout, "package.json")).overrides as Deps;
	const manifest = readJson(join(VENDOR, "package.json"));
	const lock: Lock = {
		package: String(manifest.name),
		version: String(manifest.version),
		repository: "nyxon-tech/nyxon-tech",
		path: UPSTREAM_PATH,
		commit: git("rev-parse", "HEAD"),
		overrides: Object.fromEntries(SHARED_OVERRIDES.map((name) => [name, root[name]])),
		sha256: treeHash(entries),
	};
	writeFileSync(LOCK, `${JSON.stringify(lock, null, 2)}\n`);
	console.log(
		`@nyxon/nasim ${lock.version} from ${lock.commit.slice(0, 12)}, ${entries.length} files`,
	);
	for (const problem of appProblems(lock)) console.log(`  fix in package.json: ${problem}`);
}

function check(against?: string) {
	const lock = readJson(LOCK) as unknown as Lock;
	const problems = appProblems(lock);
	if (treeHash(walk(VENDOR)) !== lock.sha256) {
		problems.unshift("vendor/nasim was edited by hand: change Nasim in NYXON, then run nasim:sync");
	}
	if (against && treeHash(upstreamEntries(join(against, UPSTREAM_PATH))) !== lock.sha256) {
		problems.push(
			`${against} holds another Nasim than ${lock.commit.slice(0, 12)}: run nasim:sync`,
		);
	}
	if (problems.length) {
		for (const problem of problems) console.error(problem);
		process.exit(1);
	}
	console.log(`@nyxon/nasim ${lock.version} matches NYXON ${lock.commit.slice(0, 12)}`);
}

if (import.meta.main) {
	const [command, ...rest] = process.argv.slice(2);
	if (command === "sync" && rest[0]) sync(rest[0]);
	else if (command === "check") check(rest[0] === "--against" ? rest[1] : undefined);
	else {
		console.error(
			"usage: bun scripts/nasim.ts sync <nyxon checkout> | check [--against <nyxon checkout>]",
		);
		process.exit(2);
	}
}
