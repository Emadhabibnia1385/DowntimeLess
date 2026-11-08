import { countryName, flagOf, placeLine } from "@/strings";

type Located = { role: string; country?: string | null; city?: string | null; org?: string | null };

// A relay reports the foreign transit it exits through (e.g. Frankfurt); it always reads as Iran.
export function whereOf(server: Located): { flag: string; place: string } {
	if (server.role === "relay") return { flag: flagOf("IR"), place: countryName("IR") };
	return { flag: flagOf(server.country), place: placeLine(server) };
}
