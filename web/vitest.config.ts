import { fileURLToPath, URL } from "node:url";
import babel from "@rolldown/plugin-babel";
import { reactCompilerPreset } from "@vitejs/plugin-react";
import Icons from "unplugin-icons/vite";
import { defineConfig } from "vitest/config";

// Logic tests run in node, *.test.tsx in jsdom with the React Compiler (which can hide a gap).
export default defineConfig({
	resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
	plugins: [
		babel({ presets: [reactCompilerPreset()] }),
		Icons({ compiler: "jsx", jsx: "react", autoInstall: false }),
	],
	test: {
		projects: [
			{
				extends: true,
				test: {
					name: "logic",
					environment: "node",
					include: [
						"src/**/*.test.ts",
						"scripts/**/*.test.ts",
						"e2e/**/*.test.ts",
						"mock/**/*.test.ts",
					],
				},
			},
			{
				extends: true,
				test: {
					name: "ui",
					environment: "jsdom",
					include: ["src/**/*.test.tsx"],
					setupFiles: ["src/test/setup.ts"],
				},
			},
		],
	},
});
