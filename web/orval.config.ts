import { defineConfig } from "orval";

// The API client is generated from the backend's OpenAPI document (ADR-09): never edit the output.
const input = { target: "./openapi.json" };

// A second biome pass: one pass can leave a long description in a shape biome would still change.
const hooks = { afterAllFilesWrite: "biome format --write" };

export default defineConfig({
	api: {
		input,
		hooks,
		output: {
			mode: "tags-split",
			client: "react-query",
			httpClient: "fetch",
			target: "./src/api/generated",
			schemas: "./src/api/generated/model",
			clean: true,
			formatter: "biome",
			override: {
				mutator: { path: "./src/api/transport.ts", name: "apiFetch" },
				fetch: { includeHttpResponseReturnType: false },
				query: { queryOptions: { path: "./src/api/queryDefaults.ts", name: "queryDefaults" } },
			},
		},
	},
	zod: {
		input,
		hooks,
		output: {
			mode: "tags-split",
			client: "zod",
			target: "./src/api/zod",
			fileExtension: ".zod.ts",
			clean: true,
			formatter: "biome",
			override: { zod: { version: 4 } },
		},
	},
});
