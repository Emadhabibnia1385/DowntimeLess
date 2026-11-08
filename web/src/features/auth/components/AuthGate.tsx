import { ErrorState } from "@nyxon/nasim";
import { useNavigate, useRouter } from "@tanstack/react-router";
import { type ReactNode, useEffect } from "react";
import { errorMessage } from "@/api/transport";
import { setTabWorkspace, tabWorkspace } from "@/api/workspace";
import { PageSkeleton } from "@/app/shell/PageSkeleton";
import { useMe } from "../session";
import { useWorkspaceRecovery } from "../useWorkspaceRecovery";

// Lets a signed-in person through; anyone else goes to the login page and comes back after.
export function AuthGate({ children }: { children: ReactNode }) {
	const me = useMe();
	useWorkspaceRecovery();
	const router = useRouter();
	const navigate = useNavigate();
	const signedOut = me.isError && me.error.status === 401;
	const landed = me.data?.workspace?.id;
	// a new tab starts where the master landed it; from then on it names its own workspace
	useEffect(() => {
		if (landed && tabWorkspace() === null) setTabWorkspace(landed);
	}, [landed]);
	// Read the address in the effect; following it as state bounces /login to /login forever.
	useEffect(() => {
		if (!signedOut) return;
		const { pathname, href } = router.state.location;
		if (pathname !== "/login")
			void navigate({ to: "/login", search: { redirect: href }, replace: true });
	}, [signedOut, router, navigate]);
	if (me.isPending || signedOut) return <PageSkeleton />;
	if (me.isError)
		return <ErrorState message={errorMessage(me.error)} onRetry={() => void me.refetch()} />;
	return children;
}
