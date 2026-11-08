import { useCategoriesList } from "@/api/generated/categories/categories";

const REFRESH_MS = 15_000;

/** The categories, refreshed with the fleet every 15 seconds. */
export function useCategories() {
	return useCategoriesList({ query: { refetchInterval: REFRESH_MS } });
}
