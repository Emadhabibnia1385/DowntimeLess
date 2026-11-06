import { useEffect, useRef } from "react";

/** Calls `onDone` once for each new value (never for none), however often the caller re-renders. */
export function useOnceDone<T>(value: T | undefined, onDone: (value: T) => void) {
	const handled = useRef<T | undefined>(undefined);
	useEffect(() => {
		if (value === undefined || handled.current === value) return;
		handled.current = value;
		onDone(value);
	}, [value, onDone]);
}
