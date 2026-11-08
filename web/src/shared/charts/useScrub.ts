import { type KeyboardEvent, type PointerEvent, useState } from "react";

/** The point under the pointer or chosen with the arrow keys; null when none. */
export function useScrub({
	count,
	reversed,
	indexAt,
}: {
	count: number;
	reversed: boolean;
	/** The nearest point for an x in the plot's own pixels. */
	indexAt: (x: number) => number;
}) {
	const [index, setIndex] = useState<number | null>(null);
	const move = (step: number) =>
		setIndex((last) => Math.min(count - 1, Math.max(0, (last ?? count - 1) + step)));
	return {
		select: setIndex,
		index: index !== null && index < count ? index : null,
		onPointerMove: (event: PointerEvent<SVGSVGElement>) => {
			const box = event.currentTarget.getBoundingClientRect();
			const scale = box.width ? event.currentTarget.viewBox.baseVal.width / box.width : 1;
			setIndex(indexAt((event.clientX - box.left) * scale));
		},
		onPointerLeave: (event: PointerEvent<SVGSVGElement>) => {
			if (event.pointerType === "mouse") setIndex(null);
		},
		onFocus: () => setIndex((last) => last ?? count - 1),
		onBlur: () => setIndex(null),
		onKeyDown: (event: KeyboardEvent) => {
			const toward = reversed ? -1 : 1;
			const keys: Record<string, () => void> = {
				ArrowLeft: () => move(-toward),
				ArrowRight: () => move(toward),
				Home: () => setIndex(0),
				End: () => setIndex(count - 1),
				Escape: () => setIndex(null),
			};
			const act = keys[event.key];
			if (!act) return;
			event.preventDefault();
			act();
		},
	};
}
