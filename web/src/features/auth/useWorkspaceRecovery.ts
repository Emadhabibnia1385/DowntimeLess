import { toast } from "@nyxon/nasim";
import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { authWorkspaces } from "@/api/generated/auth/auth";
import { ApiError } from "@/api/transport";
import { setTabWorkspace } from "@/api/workspace";
import { t } from "@/strings";

const gone = (error: unknown) => error instanceof ApiError && error.code === "workspace.not_found";

let busy = false;

/** The tab's workspace is not mine any more: move to my own (else my first) and say so. */
export async function recoverWorkspace(queryClient: QueryClient): Promise<void> {
	if (busy) return;
	busy = true;
	try {
		const spaces = await authWorkspaces();
		const next = spaces.find((space) => space.is_personal) ?? spaces[0];
		setTabWorkspace(next ? next.id : null);
		await queryClient.resetQueries();
		if (next) toast.warning(t.workspace.gone(next.name));
	} catch {
		setTabWorkspace(null);
	} finally {
		busy = false;
	}
}

// Any answer `workspace.not_found`, from a query or a change, starts the move once.
export function useWorkspaceRecovery() {
	const queryClient = useQueryClient();
	useEffect(() => {
		const watch = (event: { type: string; action?: { type: string; error?: unknown } }) => {
			if (event.type === "updated" && event.action?.type === "error" && gone(event.action.error))
				void recoverWorkspace(queryClient);
		};
		const stopQueries = queryClient.getQueryCache().subscribe(watch);
		const stopMutations = queryClient.getMutationCache().subscribe(watch);
		return () => {
			stopQueries();
			stopMutations();
		};
	}, [queryClient]);
}
