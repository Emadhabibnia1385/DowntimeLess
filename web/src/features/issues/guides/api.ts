import { useReportsPlaybook, useReportsPlaybooks } from "@/api/generated/reports/reports";

// Guides change only with a new master release: no polling.
const STALE_MS = 60 * 60_000;

export function useGuideIndex() {
	return useReportsPlaybooks({ lang: "fa" }, { query: { staleTime: STALE_MS } });
}

export function useGuide(code: string | null) {
	return useReportsPlaybook(
		code ?? "",
		{ lang: "fa" },
		{ query: { enabled: code !== null, staleTime: STALE_MS } },
	);
}
