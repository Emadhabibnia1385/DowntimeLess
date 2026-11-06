import { ErrorState } from "@nyxon/nasim";
import { useNavigate, useRouter } from "@tanstack/react-router";
import { type ReactNode, useEffect } from "react";
import { errorMessage } from "@/api/transport";
import { PageSkeleton } from "@/app/shell/PageSkeleton";
import { useMe } from "../session";

// Lets a signed-in person through; anyone else goes to the login page and comes back after.
export function AuthGate({ children }: { children: ReactNode }) {
	const me = useMe();
	const router = useRouter();
	const navigate = useNavigate();
	const signedOut = me.isError && me.error.status === 401;
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
