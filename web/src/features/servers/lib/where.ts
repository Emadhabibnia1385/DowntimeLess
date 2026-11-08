import { countryName, flagOf, placeLine } from "@/strings";

type Located = { role: string; country?: string | null; city?: string | null; org?: string | null };

// An old agent places a relay by its foreign exit; until it reports Iran, show only Iran.
export function whereOf(server: Located): { flag: string; place: string } {
	if (server.role === "relay" && server.country !== "IR") {
		return { flag: flagOf("IR"), place: countryName("IR") };
	}
	return { flag: flagOf(server.country), place: placeLine(server) };
}
