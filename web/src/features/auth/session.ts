import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { getAuthMeQueryKey, useAuthLogout, useAuthMe } from "@/api/generated/auth/auth";
import type { UserOut } from "@/api/generated/model";

/** Who is signed in; a 401 here means nobody. The answer is kept until a sign-out. */
export function useMe() {
	return useAuthMe({ query: { retry: false, staleTime: Number.POSITIVE_INFINITY } });
}

export type Role = "owner" | "admin" | "viewer";

/** The signed-in person's role; only called under the auth gate, so `me` is there. */
export function useRole(): Role {
	const role = useMe().data?.role;
	return role === "owner" || role === "admin" ? role : "viewer";
}

/** Whether the person may change things (admins and the owner; a viewer only looks). */
export function useCanManage(): boolean {
	return useRole() !== "viewer";
}

/** Remembers the user a sign-in returned so the gate lets them through at once. */
export function useStartSession() {
	const queryClient = useQueryClient();
	return (user: UserOut) => queryClient.setQueryData(getAuthMeQueryKey(), user);
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
					queryClient.clear();
					void navigate({ to: "/login", search: { redirect: undefined }, replace: true });
				},
			}),
	};
}
