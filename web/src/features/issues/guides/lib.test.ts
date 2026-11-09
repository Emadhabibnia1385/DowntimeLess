import { describe, expect, it } from "vitest";
import type { PlaybookItem } from "@/api/generated/model";
import { filterGuides, fold, groupGuides, guideItems } from "./lib";

const pb = (
	code: string,
	theme: string,
	title_fa: string | null,
	meaning_fa = "",
): PlaybookItem => ({
	code,
	theme,
	title: code,
	summary_fa: "",
	detector: "live",
	title_fa,
	meaning_fa,
});

const items = guideItems([
	pb("disk", "host", "دیسک رو به پر شدن است", "درصد استفادهٔ دیسک بالاست"),
	pb("dnat_missing", "tunnel", "جدول یا قوانین DNAT از بین رفته", "جدول relay_dnat نیست"),
	pb("node_down", "node", "نود در پنل وصل نیست"),
	pb("quota_exhausted", "quota", null),
	pb("odd", "dns", "چیزی دیگر"),
]);

describe("guide list", () => {
	it("keeps only the playbooks that have a guide for people", () => {
		expect(items.map((i) => i.code)).toEqual(["disk", "dnat_missing", "node_down", "odd"]);
	});

	it("finds by code, by words of the title and across Arabic letter forms", () => {
		expect(filterGuides(items, "DNAT").map((i) => i.code)).toEqual(["dnat_missing"]);
		expect(filterGuides(items, "node down").map((i) => i.code)).toEqual(["node_down"]);
		expect(filterGuides(items, "  ديسك ").map((i) => i.code)).toEqual(["disk"]);
		expect(filterGuides(items, "نود وصل").map((i) => i.code)).toEqual(["node_down"]);
		expect(filterGuides(items, "")).toHaveLength(4);
		expect(filterGuides(items, "zzz")).toEqual([]);
		expect(fold("استفاده‌ی")).toBe("استفادهی");
	});

	it("groups by theme in a fixed order and puts unknown themes last", () => {
		expect(groupGuides(items).map((g) => [g.theme, g.items.length])).toEqual([
			["host", 1],
			["tunnel", 1],
			["node", 1],
			["other", 1],
		]);
	});
});
