import { useBottomBar } from "@nyxon/nasim";
import { Link } from "@tanstack/react-router";
import { tv } from "tailwind-variants";
import { t } from "@/strings";
import { NAV, type NavItem } from "./nav";

const bar = tv({
	slots: {
		root: "fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface px-safe pb-(--nasim-safe-bottom) lg:hidden",
		list: "mx-auto flex max-w-xl items-stretch",
		link: "flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 rounded-lg px-1 py-1.5 text-center text-xs leading-tight font-medium text-muted outline-none transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus data-[status=active]:text-accent-soft-foreground",
		// the centre action: a raised circle that overlaps the bar's top edge
		home: "group flex min-h-14 w-full -mt-7 flex-col items-center gap-1 rounded-lg pb-1.5 text-center text-xs leading-tight font-medium text-muted outline-none transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus data-[status=active]:font-semibold data-[status=active]:text-accent-soft-foreground",
		orb: "grid size-14 place-items-center rounded-full bg-accent text-accent-foreground shadow-md ring-4 ring-surface transition-colors group-hover:bg-accent-hover group-data-[status=active]:outline-2 group-data-[status=active]:outline-offset-[3px] group-data-[status=active]:outline-accent",
	},
});

function Tab({ item }: { item: NavItem }) {
	const slots = bar();
	return (
		<li className="flex flex-1">
			<Link to={item.to} activeOptions={{ exact: item.to === "/" }} className={slots.link()}>
				<item.icon aria-hidden className="size-6" />
				<span>{item.label}</span>
			</Link>
		</li>
	);
}

// The phone bar: the screens used most, the dashboard raised in the middle (also in RTL).
export function BottomBar() {
	const ref = useBottomBar<HTMLElement>();
	const slots = bar();
	const primary = NAV.filter((item) => item.primary);
	const home = primary.find((item) => item.to === "/");
	const others = primary.filter((item) => item.to !== "/");
	const half = Math.ceil(others.length / 2);
	return (
		<nav ref={ref} aria-label={t.nav.quick} className={slots.root()}>
			<ul className={slots.list()}>
				{others.slice(0, half).map((item) => (
					<Tab key={item.to} item={item} />
				))}
				{home ? (
					<li data-center className="flex w-20 shrink-0 items-start justify-center">
						<Link to={home.to} activeOptions={{ exact: true }} className={slots.home()}>
							<span className={slots.orb()}>
								<home.icon aria-hidden className="size-7" />
							</span>
							<span>{home.label}</span>
						</Link>
					</li>
				) : null}
				{others.slice(half).map((item) => (
					<Tab key={item.to} item={item} />
				))}
			</ul>
		</nav>
	);
}
