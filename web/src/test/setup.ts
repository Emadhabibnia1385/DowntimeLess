import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup);

// jsdom has no layout engine; stub what React Aria and HeroUI probe for.
window.matchMedia ??= (query: string) =>
	({
		matches: false,
		media: query,
		onchange: null,
		addEventListener() {},
		removeEventListener() {},
		addListener() {},
		removeListener() {},
		dispatchEvent: () => false,
	}) as MediaQueryList;

window.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
};

// axe probes the canvas for some checks; jsdom has none and would print "not implemented".
HTMLCanvasElement.prototype.getContext = () => null;
