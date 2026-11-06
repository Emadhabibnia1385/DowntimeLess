import { QueryCache, QueryClient } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { getAuthMeQueryKey } from "@/api/generated/auth/auth";
import { DEFAULT_QUERY_OPTIONS } from "@/api/queryDefaults";
import { ApiError } from "@/api/transport";
import "@/index.css";
import { AppProviders } from "./providers";
import { router } from "./router";

const ME_KEY = getAuthMeQueryKey();

// A 401 from any screen means the session ended: ask who is signed in, and the gate reacts.
const queryClient: QueryClient = new QueryClient({
	defaultOptions: { queries: DEFAULT_QUERY_OPTIONS },
	queryCache: new QueryCache({
		onError: (error, query) => {
			if (error instanceof ApiError && error.status === 401 && query.queryKey[0] !== ME_KEY[0]) {
				void queryClient.resetQueries({ queryKey: ME_KEY });
			}
		},
	}),
});

const root = document.getElementById("root");
if (!root) throw new Error("index.html has no #root");

createRoot(root).render(
	<StrictMode>
		<AppProviders queryClient={queryClient} router={router} />
	</StrictMode>,
);
