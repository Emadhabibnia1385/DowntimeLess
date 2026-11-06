import { describe, expect, it } from "vitest";
import { pinDrift, treeHash, vendoredManifest } from "./nasim.ts";

describe("vendoredManifest", () => {
	it("keeps what an importer needs and drops the library's own tooling", () => {
		const upstream = {
			name: "@nyxon/nasim",
			version: "0.6.0",
			private: true,
			type: "module",
			sideEffects: ["**/*.css"],
			exports: { ".": "./src/index.ts" },
			scripts: { test: "vitest run" },
			dependencies: { "@heroui/react": "3.2.6" },
			peerDependencies: { react: "^19.2.0" },
			devDependencies: { vitest: "4.1.11", react: "19.2.8" },
		};
		expect(vendoredManifest(upstream)).toEqual({
			name: "@nyxon/nasim",
			version: "0.6.0",
			private: true,
			type: "module",
			sideEffects: ["**/*.css"],
			exports: { ".": "./src/index.ts" },
			dependencies: { "@heroui/react": "3.2.6" },
			peerDependencies: { react: "^19.2.0" },
		});
	});
});

describe("treeHash", () => {
	it("depends on every path and byte, not on the order files are listed", () => {
		const a = { path: "src/a.ts", bytes: Buffer.from("a") };
		const b = { path: "src/b.ts", bytes: Buffer.from("b") };
		expect(treeHash([a, b])).toBe(treeHash([b, a]));
		expect(treeHash([a, b])).not.toBe(treeHash([a, { ...b, bytes: Buffer.from("B") }]));
		expect(treeHash([a, b])).not.toBe(treeHash([a, { ...b, path: "src/c.ts" }]));
	});
});

describe("pinDrift", () => {
	it("names a package the app pins to another version than Nasim does", () => {
		const nasim = { "@heroui/react": "3.2.6", zod: "4.6.5", "react-hook-form": "7.81.0" };
		const app = { "@heroui/react": "3.2.6", zod: "^4.4.3" };
		expect(pinDrift(nasim, app)).toEqual(["zod: the app has ^4.4.3, Nasim 4.6.5"]);
	});
});
