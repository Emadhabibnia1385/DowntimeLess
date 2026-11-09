import type { PlaybookItem } from "@/api/generated/model";
import { t } from "@/strings";

export type GuideItem = { code: string; theme: string; title: string; meaning: string };
export type GuideGroup = { theme: string; label: string; items: GuideItem[] };

const THEMES: Record<string, string> = t.issueGuides.themes;
const ORDER = Object.keys(THEMES);

/** Arabic letter forms, joiners and case folded away: «كد» finds «کد», "DNAT" finds "dnat". */
export function fold(text: string): string {
	return text
		.replace(/\u064a|\u0649/g, "\u06cc")
		.replace(/\u0643/g, "\u06a9")
		.replace(/\u200c|\u200d|\p{Mn}/gu, "")
		.toLowerCase()
		.replace(/\s+/g, " ")
		.trim();
}

/** The playbooks that have a guide for people, as the guides tab lists them. */
export function guideItems(playbooks: readonly PlaybookItem[]): GuideItem[] {
	return playbooks.flatMap((p) =>
		p.title_fa
			? [{ code: p.code, theme: p.theme, title: p.title_fa, meaning: p.meaning_fa ?? "" }]
			: [],
	);
}

/** Every word of the query must appear in the code, the title or the meaning. */
export function filterGuides(items: readonly GuideItem[], query: string): GuideItem[] {
	const words = fold(query).split(" ").filter(Boolean);
	if (words.length === 0) return [...items];
	return items.filter((item) => {
		const hay = fold(`${item.code} ${item.code.replace(/_/g, " ")} ${item.title} ${item.meaning}`);
		return words.every((word) => hay.includes(word));
	});
}

/** One group per theme in a fixed order; a theme without a label goes under «سایر». */
export function groupGuides(items: readonly GuideItem[]): GuideGroup[] {
	const groups = new Map<string, GuideItem[]>();
	for (const item of items) {
		const theme = item.theme in THEMES ? item.theme : "other";
		groups.set(theme, [...(groups.get(theme) ?? []), item]);
	}
	return ORDER.filter((theme) => groups.has(theme)).map((theme) => ({
		theme,
		label: THEMES[theme],
		items: groups.get(theme) ?? [],
	}));
}
