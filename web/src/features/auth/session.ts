import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { getAuthMeQueryKey, useAuthLogout, useAuthMe } from "@/api/generated/auth/auth";
import type { UserOut, WorkspaceOut } from "@/api/generated/model";
import { setTabWorkspace } from "@/api/workspace";

/** Who is signed in and where; asked again after a minute or on window focus. */
export function useMe() {
	return useAuthMe({ query: { retry: false, staleTime: 60_000, refetchOnWindowFocus: true } });
}

export type Role = "owner" | "admin" | "operator" | "viewer";

const RANK: Record<Role, number> = { viewer: 1, operator: 2, admin: 3, owner: 4 };

export function asRole(role: string | undefined): Role {
	return role === "owner" || role === "admin" || role === "operator" ? role : "viewer";
}

/** My role in the active workspace; only called under the auth gate, so `me` is there. */
export function useRole(): Role {
	return asRole(useMe().data?.role);
}

/** Whether my role in this workspace reaches `least` (the server checks the same ranks). */
export function useHasRole(least: Role): boolean {
	return RANK[useRole()] >= RANK[least];
}

/** Admins and the owner change things; operators and viewers do not. */
export function useCanManage(): boolean {
	return useHasRole("admin");
}

/** Operators and up run the safe checks and diagnostics. */
export function useCanCheck(): boolean {
	return useHasRole("operator");
}

/** The workspace this session acts in. */
export function useWorkspace(): WorkspaceOut | undefined {
	return useMe().data?.workspace;
}

/** Remembers the user a sign-in returned so the gate lets them through at once. */
export function useStartSession() {
	const queryClient = useQueryClient();
	return (user: UserOut) => {
		setTabWorkspace(user.workspace.id);
		queryClient.setQueryData(getAuthMeQueryKey(), user);
	};
}

/** Ends the session on the master, forgets everything cached, and goes to the login page. */
export function useSignOut() {
	const queryClient = useQueryClient();
	const navigate = useNavigate();
	const logout = useAuthLogout();
	return {
		isPending: logout.isPending,
		signOut: () =>
			logout.mutate(undefined, {
				onSettled: () => {
					setTabWorkspace(null);
					queryClient.clear();
					void navigate({ to: "/login", search: { redirect: undefined }, replace: true });
				},
			}),
	};
}
