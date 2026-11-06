import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { authTelegramPoll, useAuthTelegramStart } from "@/api/generated/auth/auth";
import type { UserOut } from "@/api/generated/model";
import { ApiError, errorMessage } from "@/api/transport";
import {
	type PendingLogin,
	POLL_MS,
	outcomeOf,
	pendingFrom,
	readPending,
	writePending,
} from "./pending";
import { useOnceDone } from "./useOnceDone";

// A 4xx is the master's answer (request gone, asking too often): asking again repeats it.
const isRefusal = (error: unknown): error is ApiError =>
	error instanceof ApiError && error.status >= 400 && error.status < 500;

/** Sign in through the bot: ask for a link, poll until it is approved, then hand over the user. */
export function useTelegramLogin(onDone: (user: UserOut) => void) {
	const [pending, setPending] = useState<PendingLogin | null>(() => readPending());
	const [startFailure, setStartFailure] = useState<string | null>(null);
	const start = useAuthTelegramStart();

	const poll = useQuery({
		queryKey: ["telegram-login", pending?.challengeId],
		queryFn: async () =>
			outcomeOf(
				await authTelegramPoll({
					challenge_id: pending?.challengeId ?? 0,
					poll_secret: pending?.pollSecret ?? "",
				}),
				// the query only runs while `pending` is set
				pending as PendingLogin,
				Date.now(),
			),
		enabled: pending !== null,
		// a dropped request is not a refusal: ask again until the link's own deadline
		refetchInterval: (query) =>
			isRefusal(query.state.error) ||
			query.state.data?.kind === "failed" ||
			query.state.data?.kind === "approved"
				? false
				: POLL_MS,
		refetchIntervalInBackground: true,
		retry: false,
		gcTime: 0,
	});

	const outcome = poll.data;
	const refusal = isRefusal(poll.error) ? poll.error : null;
	const finished = (outcome !== undefined && outcome.kind !== "wait") || refusal !== null;
	useOnceDone(outcome?.kind === "approved" ? outcome.user : undefined, onDone);
	useEffect(() => {
		if (finished) writePending(null);
	}, [finished]);

	const begin = () => {
		setStartFailure(null);
		start.mutate(undefined, {
			onSuccess: (started) => {
				const next = pendingFrom(started, Date.now());
				writePending(next);
				setPending(next);
			},
			onError: (error) => setStartFailure(errorMessage(error)),
		});
	};

	const cancel = () => {
		writePending(null);
		setPending(null);
	};

	return {
		deepLink: pending && !finished ? pending.deepLink : null,
		isStarting: start.isPending,
		failure:
			startFailure ??
			(outcome?.kind === "failed" ? outcome.message : refusal ? errorMessage(refusal) : null),
		begin,
		cancel,
	};
}
