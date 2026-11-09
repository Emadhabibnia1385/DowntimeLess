import { Button, EmptyState, SearchBox, SectionCard, SkeletonRows } from "@nyxon/nasim";
import { useState } from "react";
import { Loadable } from "@/shared/Loadable";
import { formatNumber, t } from "@/strings";
import { useGuideIndex } from "./api";
import { GuideDialog, type GuideTarget } from "./GuideDialog";
import { filterGuides, type GuideItem, groupGuides, guideItems } from "./lib";

const G = t.issueGuides;

function Row({ item, onOpen }: { item: GuideItem; onOpen: (item: GuideItem) => void }) {
	return (
		<li className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
			<div className="flex min-w-0 flex-col gap-1">
				<span className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
					<span className="font-semibold">{item.title}</span>
					<span dir="ltr" className="font-mono text-xs text-muted">
						{item.code}
					</span>
				</span>
				<span className="line-clamp-2 text-sm text-muted">{item.meaning}</span>
			</div>
			<Button
				size="sm"
				variant="secondary"
				className="shrink-0 self-start sm:self-center"
				aria-label={G.open(item.title)}
				onPress={() => onOpen(item)}
			>
				{G.action}
			</Button>
		</li>
	);
}

// Every guide for people, findable by code or by words of its title.
export function GuidesTab() {
	const index = useGuideIndex();
	const [query, setQuery] = useState("");
	const [target, setTarget] = useState<GuideTarget | null>(null);
	const open = (item: GuideItem) => setTarget({ code: item.code, title: item.title });
	return (
		<div className="flex flex-col gap-4">
			<p className="text-sm text-muted">{G.intro}</p>
			<div className="max-w-xl">
				<SearchBox
					label={G.search}
					placeholder={G.searchPlaceholder}
					value={query}
					onChange={setQuery}
				/>
			</div>
			<Loadable query={index} skeleton={<SkeletonRows />}>
				{(data) => {
					const groups = groupGuides(filterGuides(guideItems(data.playbooks), query));
					if (groups.length === 0)
						return <EmptyState title={G.noMatchTitle} description={G.noMatch} />;
					return groups.map((group) => (
						<SectionCard
							key={group.theme}
							title={group.label}
							description={G.count(formatNumber(group.items.length))}
						>
							<ul className="flex flex-col divide-y divide-border">
								{group.items.map((item) => (
									<Row key={item.code} item={item} onOpen={open} />
								))}
							</ul>
						</SectionCard>
					));
				}}
			</Loadable>
			<GuideDialog target={target} onClose={() => setTarget(null)} />
		</div>
	);
}
