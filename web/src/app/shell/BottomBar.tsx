import { useBottomBar } from "@nyxon/nasim";
import { Link } from "@tanstack/react-router";
import { tv } from "tailwind-variants";
import { t } from "@/strings";
import { NAV } from "./nav";

const bar = tv({
	slots: {
		root: "fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface px-safe pb-(--nasim-safe-bottom) lg:hidden",
		list: "mx-auto flex max-w-xl items-stretch justify-around",
		link: "flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 rounded-lg px-1 py-1.5 text-xs font-medium text-muted outline-none transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus data-[status=active]:text-accent-soft-foreground",
	},
});

// The phone's bottom bar: the screens used most; the menu button holds the rest.
export function BottomBar() {
	const ref = useBottomBar<HTMLElement>();
	const slots = bar();
	return (
		<nav ref={ref} aria-label={t.nav.quick} className={slots.root()}>
			<ul className={slots.list()}>
				{NAV.filter((item) => item.primary).map((item) => (
					<li key={item.to} className="flex flex-1">
						<Link to={item.to} activeOptions={{ exact: item.to === "/" }} className={slots.link()}>
							<item.icon aria-hidden className="size-6" />
							<span>{item.label}</span>
						</Link>
					</li>
				))}
			</ul>
		</nav>
	);
}
