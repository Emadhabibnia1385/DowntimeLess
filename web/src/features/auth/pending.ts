import type { PollResult, StartResult, UserOut } from "@/api/generated/model";
import { t } from "@/strings";

// The same page reload should not lose a login in progress.
const KEY = "downtimeless.pending-login";

export const POLL_MS = 2000;

export type PendingLogin = {
	challengeId: number;
	pollSecret: string;
	deepLink: string;
	/** Epoch milliseconds, by the browser's clock. */
	expiresAt: number;
};

export type PollOutcome =
	| { kind: "wait" }
	| { kind: "approved"; user: UserOut }
	| { kind: "failed"; message: string };

type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const defaultStore = (): Store | undefined => {
	try {
		return sessionStorage;
	} catch {
		return undefined;
	}
};

export function pendingFrom(started: StartResult, now: number): PendingLogin {
	return {
		challengeId: started.challenge_id,
		pollSecret: started.poll_secret,
		deepLink: started.deep_link,
		expiresAt: now + started.expires_in * 1000,
	};
}

export function readPending(now = Date.now(), store = defaultStore()): PendingLogin | null {
	try {
		const raw = store?.getItem(KEY);
		const pending = raw ? (JSON.parse(raw) as PendingLogin) : null;
		return pending && pending.expiresAt > now ? pending : null;
	} catch {
		return null;
	}
}

export function writePending(pending: PendingLogin | null, store = defaultStore()) {
	try {
		if (pending) store?.setItem(KEY, JSON.stringify(pending));
		else store?.removeItem(KEY);
	} catch {
		// a reload during sign-in just starts again
	}
}

/** What one poll answer means: keep waiting, signed in, or the end of this attempt. */
export function outcomeOf(result: PollResult, pending: PendingLogin, now: number): PollOutcome {
	if (result.status === "approved" && result.user) return { kind: "approved", user: result.user };
	if (result.status === "denied") return { kind: "failed", message: t.login.denied };
	if (result.status === "expired" || now > pending.expiresAt) {
		return { kind: "failed", message: t.login.expired };
	}
	return { kind: "wait" };
}

/** Where to go after signing in: only a path on this site, never another address. */
export function safeRedirect(path: string | undefined): string {
	return path?.startsWith("/") && !path.startsWith("//") && !path.startsWith("/login") ? path : "/";
}
