import { ErrorState } from "@nyxon/nasim";
import { Navigate, useRouterState } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { errorMessage } from "@/api/transport";
import { PageSkeleton } from "@/app/shell/PageSkeleton";
import { useMe } from "../session";

// Lets a signed-in person through; anyone else goes to the login page and comes back after.
export function AuthGate({ children }: { children: ReactNode }) {
	const me = useMe();
	const here = useRouterState({ select: (state) => state.location.href });
	if (me.isPending) return <PageSkeleton />;
	if (me.isError) {
		if (me.error.status === 401) {
			return <Navigate to="/login" search={{ redirect: here }} replace />;
		}
		return <ErrorState message={errorMessage(me.error)} onRetry={() => void me.refetch()} />;
	}
	return children;
}
