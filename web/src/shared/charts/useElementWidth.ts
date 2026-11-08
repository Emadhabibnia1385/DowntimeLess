import { type RefObject, useLayoutEffect, useState } from "react";

const FALLBACK = 640;

/** The width of an element in pixels (kept current), and whether it is laid out right to left. */
export function useElementBox(ref: RefObject<HTMLElement | null>): { width: number; rtl: boolean } {
	const [box, setBox] = useState({ width: FALLBACK, rtl: true });
	useLayoutEffect(() => {
		const element = ref.current;
		if (!element) return;
		const read = () => {
			const width = Math.round(element.getBoundingClientRect().width) || FALLBACK;
			const rtl = getComputedStyle(element).direction === "rtl";
			setBox((last) => (last.width === width && last.rtl === rtl ? last : { width, rtl }));
		};
		read();
		const observer = new ResizeObserver(read);
		observer.observe(element);
		return () => observer.disconnect();
	}, [ref]);
	return box;
}
