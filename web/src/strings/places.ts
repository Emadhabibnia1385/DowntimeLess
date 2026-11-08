// English names for where a server is (country, city, data center) and its flag.
const DATACENTERS: [RegExp, string][] = [
	[/hetzner/i, "Hetzner"],
	[/netcup/i, "netcup"],
	[/leaseweb/i, "Leaseweb"],
	[/ekiphost/i, "EkipHost"],
	[/sepehr sabz/i, "Sepehr Sabz"],
	[/rayaneh gostar/i, "Rayaneh Gostar"],
	[/taymaz/i, "Taymaz Gostaran"],
	[/pccw/i, "PCCW Global"],
];

const LEGAL_SUFFIX = /[\s,]+(gmbh|b\.v\.|inc\.?|ltd\.?|limited|llc|pte\.?|s\.a\.|ag)\b.*$/i;

const REGIONS = new Intl.DisplayNames(["en"], { type: "region" });

/** The flag emoji of a two-letter country code; empty for anything else. */
export function flagOf(country: string | null | undefined): string {
	if (!country || !/^[A-Za-z]{2}$/.test(country)) return "";
	return String.fromCodePoint(
		...[...country.toUpperCase()].map((letter) => 0x1f1a5 + letter.charCodeAt(0)),
	);
}

export function countryName(country: string | null | undefined): string {
	if (!country || !/^[A-Za-z]{2}$/.test(country)) return "";
	try {
		return REGIONS.of(country.toUpperCase()) ?? country;
	} catch {
		return country;
	}
}

export function datacenterName(org: string | null | undefined): string {
	if (!org) return "";
	return DATACENTERS.find(([pattern]) => pattern.test(org))?.[1] ?? org.replace(LEGAL_SUFFIX, "");
}

/** "Germany · Nuremberg · netcup": the parts a report gave, in that order. */
export function placeLine(server: {
	country?: string | null;
	city?: string | null;
	org?: string | null;
}): string {
	return [countryName(server.country), server.city, datacenterName(server.org)]
		.filter(Boolean)
		.join(" · ");
}

/** The IPv4 address to show; an IPv6 one from an older agent is left out. */
export const ipv4Of = (ip: string | null | undefined): string =>
	ip && !ip.includes(":") ? ip : "";
