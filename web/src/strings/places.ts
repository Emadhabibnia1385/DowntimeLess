// Persian names for where a server is: country, city and data center, plus the flag.
const CITIES: Record<string, string> = {
	Manassas: "مناساس",
	Amsterdam: "آمستردام",
	Nuremberg: "نورنبرگ",
	Falkenstein: "فالکن‌اشتاین",
	Istanbul: "استانبول",
	London: "لندن",
	Helsinki: "هلسینکی",
	Singapore: "سنگاپور",
	Tehran: "تهران",
	Ramshir: "رامشیر",
	Alvand: "الوند",
	"Frankfurt am Main": "فرانکفورت",
	Milan: "میلان",
	Vienna: "وین",
};

// First match wins, so the longer or more specific names come first.
const DATACENTERS: [RegExp, string][] = [
	[/hetzner/i, "هتزنر"],
	[/netcup/i, "نت‌کاپ"],
	[/leaseweb/i, "لیزوب"],
	[/ekiphost/i, "اکیپ‌هاست"],
	[/sepehr sabz/i, "سپهر سبز"],
	[/rayaneh gostar/i, "رایانه گستر"],
	[/taymaz/i, "تیماز گستران"],
	[/pccw/i, "پی‌سی‌سی‌دابلیو"],
];

const REGIONS = new Intl.DisplayNames(["fa"], { type: "region" });

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

export const cityName = (city: string | null | undefined): string =>
	city ? (CITIES[city] ?? city) : "";

export function datacenterName(org: string | null | undefined): string {
	if (!org) return "";
	return DATACENTERS.find(([pattern]) => pattern.test(org))?.[1] ?? org;
}

/** "آلمان · نورنبرگ · نت‌کاپ": the parts a report gave, in that order. */
export function placeLine(server: {
	country?: string | null;
	city?: string | null;
	org?: string | null;
}): string {
	return [countryName(server.country), cityName(server.city), datacenterName(server.org)]
		.filter(Boolean)
		.join(" · ");
}
