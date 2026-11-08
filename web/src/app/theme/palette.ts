import type { Palette } from "@nyxon/nasim";

// Brand palette (CLAUDE.md). Light accent is #3F6E18: lime is 1.5:1 on white, so it is dark-only.
export const palette: Palette = {
	radius: "0.625rem",
	light: {
		background: "#F7FAF5",
		foreground: "#142019",
		surface: "#FFFFFF",
		surfaceSecondary: "#EEF4EA",
		surfaceTertiary: "#E4ECDE",
		overlay: "#FFFFFF",
		muted: "#4C5E50",
		border: "#D5E0CF",
		fieldBorder: "#76866F",
		accent: { fill: "#3F6E18", onFill: "#FFFFFF", tint: "#E6F0D9", text: "#3F6E18" },
		success: { fill: "#1A6B32", onFill: "#FFFFFF" },
		warning: { fill: "#8A5A00", onFill: "#FFFFFF" },
		danger: { fill: "#B42318", onFill: "#FFFFFF" },
		info: { fill: "#1F5FAA", onFill: "#FFFFFF" },
	},
	dark: {
		background: "#0B1210",
		foreground: "#F4F8F2",
		surface: "#17221C",
		surfaceSecondary: "#1E2C24",
		surfaceTertiary: "#344A2D",
		overlay: "#1E2C24",
		muted: "#B3C3AF",
		border: "#2A3B30",
		fieldBorder: "#8DA487",
		accent: { fill: "#A3E635", onFill: "#0B1210" },
		success: { fill: "#4ADE80", onFill: "#0B1210" },
		warning: { fill: "#FBBF24", onFill: "#0B1210" },
		danger: { fill: "#FF9C92", onFill: "#0B1210" },
		info: { fill: "#7DB8FF", onFill: "#0B1210" },
	},
};
