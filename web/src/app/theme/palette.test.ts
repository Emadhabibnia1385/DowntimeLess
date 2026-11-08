import { checkPalette, contrastRatio, parseHex } from "@nyxon/nasim/palette";
import { describe, expect, it } from "vitest";
import { palette } from "./palette";

const ratio = (a: string, b: string) => {
	const [x, y] = [parseHex(a), parseHex(b)];
	if (!x || !y) throw new Error("not a colour");
	return contrastRatio(x, y);
};

describe("the brand palette", () => {
	it("keeps every contrast Nasim measures, in light and dark", () => {
		expect(checkPalette(palette)).toEqual([]);
	});

	it("uses the colours the brand names", () => {
		expect(palette.dark.accent.fill).toBe("#A3E635");
		expect(palette.dark.background).toBe("#0B1210");
		expect(palette.dark.surface).toBe("#17221C");
		expect(palette.dark.foreground).toBe("#F4F8F2");
		expect(palette.dark.surfaceTertiary).toBe("#344A2D");
		expect(palette.light.background).toBe("#F7FAF5");
		expect(palette.light.surface).toBe("#FFFFFF");
		expect(palette.light.foreground).toBe("#142019");
		expect(palette.light.accent.text).toBe("#3F6E18");
	});

	it("puts dark text on the lime fill and readable green on light surfaces", () => {
		expect(ratio(palette.dark.accent.fill, palette.dark.accent.onFill)).toBeGreaterThanOrEqual(4.5);
		expect(ratio("#3F6E18", palette.light.background)).toBeGreaterThanOrEqual(4.5);
		expect(ratio("#3F6E18", palette.light.surface)).toBeGreaterThanOrEqual(4.5);
	});
});
