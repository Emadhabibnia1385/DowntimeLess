import { useSslList } from "@/api/generated/ssl/ssl";

/** Certificates from the agents and the probed domains, refreshed every 30 seconds. */
export function useSsl() {
	return useSslList({ query: { refetchInterval: 30_000 } });
}
