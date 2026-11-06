import { ErrorState } from "@nyxon/nasim";
import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { errorMessage } from "@/api/transport";
import { PageSkeleton } from "@/app/shell/PageSkeleton";

/** A query's three outcomes: a skeleton while it loads, an error with a retry, else the data. */
export function Loadable<T>({
	query,
	children,
	skeleton = <PageSkeleton />,
}: {
	query: UseQueryResult<T, Error>;
	children: (data: T) => ReactNode;
	skeleton?: ReactNode;
}) {
	if (query.isPending) return skeleton;
	if (query.isError) {
		return <ErrorState message={errorMessage(query.error)} onRetry={() => void query.refetch()} />;
	}
	return children(query.data);
}
