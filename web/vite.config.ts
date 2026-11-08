import { tanstackRouter } from "@tanstack/router-plugin/vite";
import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import Icons from "unplugin-icons/vite";
import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv } from "vite";
import { serviceWorker } from "./scripts/serviceWorkerPlugin.ts";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), "");
	// Dev-only: proxy /api to the master so the browser stays same-origin.
	const apiTarget = env.VITE_DEV_API_TARGET || "http://127.0.0.1:7390";

	return {
		// The router plugin must come before the React plugin (TanStack Router docs).
		plugins: [
			tanstackRouter({ target: "react", autoCodeSplitting: true }),
			react(),
			babel({ presets: [reactCompilerPreset()] }),
			tailwindcss(),
			// Solar icons as tree-shaken, offline SVG components (~icons/solar/*).
			Icons({ compiler: "jsx", jsx: "react", autoInstall: false }),
			// /sw.js: keeps the shell's assets for the installed app, never the API or a page.
			serviceWorker(),
		],
		resolve: {
			alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
		},
		server: {
			proxy: {
				"/api": { target: apiTarget, changeOrigin: true },
				"/llms.txt": { target: apiTarget, changeOrigin: true },
			},
		},
	};
});
