type Scheme = "light" | "dark";

// The dark-theme files carry the light strokes: each theme gets the file that reads on it.
export const brandMark = (scheme: Scheme) =>
	scheme === "dark" ? "/brand/icon-dark.png" : "/brand/icon-light.png";

export const brandLogo = (scheme: Scheme) =>
	scheme === "dark" ? "/brand/logo-dark.webp" : "/brand/logo-light.webp";
