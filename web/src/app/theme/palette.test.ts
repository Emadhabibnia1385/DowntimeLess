import { checkPalette, contrastRatio, parseHex } from "@nyxon/nasim/palette";
import { describe, expect, it } from "vitest";
import { palette } from "./palette";

const ratio = (a: string, b: string) => {
	const [x, y] = [parseHex(a), parseHex(b)];
	if (!x || !y) throw new Error("not a colour");
	return contrastRatio(x, y);
};

describe("the panel palette (Arctic Light, black and soft green dark)", () => {
	it("keeps every contrast Nasim measures, in light and dark", () => {
		expect(checkPalette(palette)).toEqual([]);
	});

	it("is slate blue in light and neutral black with a soft green in dark, with no neon lime", () => {
		expect(palette.light.accent.fill).toBe("#315C75");
		expect(palette.light.background).toBe("#F1F5F7");
		expect(palette.dark.background).toBe("#0E1012");
		expect(palette.dark.accent.fill).toBe("#8BD8A0");
		for (const mode of [palette.light, palette.dark]) {
			expect(mode.accent.fill.toLowerCase()).not.toBe("#a3e635");
			expect(mode.background.toLowerCase()).not.toBe("#000000");
		}
		// the dark canvas is a neutral grey-black: red, green and blue within a few steps of each other
		const [r, g, b] = ["1", "3", "5"].map((i) =>
			Number.parseInt(palette.dark.background.slice(Number(i), Number(i) + 2), 16),
		);
		expect(Math.max(r, g, b) - Math.min(r, g, b)).toBeLessThanOrEqual(6);
		expect(Math.max(r, g, b)).toBeLessThan(40);
	});

	it("reads clearly on the surfaces it is drawn on", () => {
		for (const mode of [palette.light, palette.dark]) {
			expect(ratio(mode.foreground, mode.background)).toBeGreaterThanOrEqual(4.5);
			expect(ratio(mode.muted, mode.background)).toBeGreaterThanOrEqual(4.5);
			expect(ratio(mode.muted, mode.surface)).toBeGreaterThanOrEqual(4.5);
			expect(ratio(mode.accent.fill, mode.accent.onFill)).toBeGreaterThanOrEqual(4.5);
			expect(ratio(mode.fieldBorder, mode.fieldBackground ?? mode.surface)).toBeGreaterThanOrEqual(
				3,
			);
			expect(ratio(mode.focus ?? mode.accent.fill, mode.background)).toBeGreaterThanOrEqual(3);
			for (const status of [mode.success, mode.warning, mode.danger, mode.info]) {
				expect(ratio(status.fill, status.onFill)).toBeGreaterThanOrEqual(4.5);
			}
		}
		expect(
			ratio(palette.light.accent.text ?? "#000000", palette.light.accent.tint ?? "#FFFFFF"),
		).toBeGreaterThanOrEqual(4.5);
	});
});
