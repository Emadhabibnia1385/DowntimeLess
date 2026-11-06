import type { NasimNavigate } from "@nyxon/nasim";
import type { AnyRouter } from "@tanstack/react-router";

type RouterLinks = { navigate: NasimNavigate; useHref: (href: string) => string };

// React Aria rebuilds every link when these change, so one router gets one pair.
const pairs = new WeakMap<AnyRouter, RouterLinks>();

/** Nasim's links move through the TanStack router: no page load, and the address it would show. */
export function routerLinks(router: AnyRouter): RouterLinks {
	let pair = pairs.get(router);
	if (!pair) {
		pair = {
			navigate: (href, options) => void router.navigate({ to: href, replace: options?.replace }),
			useHref: (href) => router.buildLocation({ to: href }).href,
		};
		pairs.set(router, pair);
	}
	return pair;
}
