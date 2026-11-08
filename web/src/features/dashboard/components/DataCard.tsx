import { LinkButton, SectionCard, TableSkeleton } from "@nyxon/nasim";
import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Loadable } from "@/shared/Loadable";

const SKELETON_ROWS = 5;

/** Tight cells fit half the page; a floor width on small screens scrolls instead of squeezing. */
export const COMPACT_TABLE = "[&_th]:px-2 [&_td]:px-2 max-xl:min-w-[30rem]";

// A titled card around one table: skeleton while loading, the shared error state with a retry.
export function DataCard<T>({
	title,
	description,
	href,
	linkLabel,
	query,
	className,
	children,
}: {
	title: string;
	description?: string;
	/** Where the "see all" button leads. */
	href?: string;
	linkLabel?: string;
	query: UseQueryResult<T, Error>;
	className?: string;
	children: (data: T) => ReactNode;
}) {
	return (
		<SectionCard
			className={className}
			title={title}
			description={description}
			actions={
				<>
					{href && linkLabel ? (
						<LinkButton href={href} size="sm" variant="secondary">
							{linkLabel}
						</LinkButton>
					) : null}
				</>
			}
		>
			<Loadable query={query} skeleton={<TableSkeleton rows={SKELETON_ROWS} />}>
				{children}
			</Loadable>
		</SectionCard>
	);
}
