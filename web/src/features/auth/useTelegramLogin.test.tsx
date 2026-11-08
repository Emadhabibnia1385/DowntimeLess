import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/transport";
import { authTelegramPoll, authTelegramStart } from "@/api/generated/auth/auth";
import { t } from "@/strings";
import { POLL_MS } from "./pending";
import { useTelegramLogin } from "./useTelegramLogin";

vi.mock("@/api/generated/auth/auth", async () => {
	const { useMutation } = await import("@tanstack/react-query");
	const authTelegramStart = vi.fn();
	return {
		authTelegramPoll: vi.fn(),
		authTelegramStart,
		useAuthTelegramStart: () => useMutation({ mutationFn: () => authTelegramStart() }),
	};
});

const user = {
	id: 1,
	name: "Emad",
	username: null,
	role: "owner",
	has_password: false,
	workspace: { id: 1, name: "فضای کار اصلی", role: "owner", is_personal: true },
	tg_username: null,
};
const started = {
	challenge_id: 9,
	deep_link: "https://t.me/bot?start=wl_x",
	expires_in: 300,
	poll_secret: "s",
};

function wrapper({ children }: { children: ReactNode }) {
	const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
	return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

// Lets promises and the next poll timer run.
const tick = (ms: number) => act(async () => void (await vi.advanceTimersByTimeAsync(ms)));

describe("useTelegramLogin", () => {
	beforeEach(() => {
		vi.useFakeTimers();
		sessionStorage.clear();
		vi.mocked(authTelegramStart).mockResolvedValue(started);
	});
	afterEach(() => {
		vi.useRealTimers();
		vi.clearAllMocks();
	});

	it("shows the link, polls every two seconds, and finishes once approved", async () => {
		const onDone = vi.fn();
		vi.mocked(authTelegramPoll)
			.mockResolvedValueOnce({ status: "pending" })
			.mockResolvedValueOnce({ status: "pending" })
			.mockResolvedValue({ status: "approved", user });
		const { result } = renderHook(() => useTelegramLogin(onDone), { wrapper });
		expect(result.current.deepLink).toBeNull();

		act(() => result.current.begin());
		await tick(0);
		expect(result.current.deepLink).toBe(started.deep_link);
		expect(sessionStorage.getItem("downtimeless.pending-login")).toContain("wl_x");

		await tick(0);
		expect(authTelegramPoll).toHaveBeenCalledTimes(1);
		await tick(POLL_MS);
		expect(authTelegramPoll).toHaveBeenCalledTimes(2);
		expect(onDone).not.toHaveBeenCalled();

		await tick(POLL_MS);
		await tick(1);
		expect(onDone).toHaveBeenCalledTimes(1);
		expect(onDone).toHaveBeenCalledWith(user);
		expect(sessionStorage.getItem("downtimeless.pending-login")).toBeNull();

		await tick(POLL_MS * 3);
		expect(authTelegramPoll).toHaveBeenCalledTimes(3);
	});

	it("reports a refusal and stops polling", async () => {
		vi.mocked(authTelegramPoll).mockResolvedValue({ status: "denied" });
		const { result } = renderHook(() => useTelegramLogin(vi.fn()), { wrapper });
		act(() => result.current.begin());
		await tick(0);
		await tick(1);
		expect(result.current.failure).toBe(t.login.denied);
		expect(result.current.deepLink).toBeNull();
		await tick(POLL_MS * 3);
		expect(authTelegramPoll).toHaveBeenCalledTimes(1);
	});

	it("stops when the master no longer knows the request", async () => {
		const gone = new ApiError(404, "auth.challenge_gone", t.apiErrors["auth.challenge_gone"]);
		vi.mocked(authTelegramPoll).mockRejectedValue(gone);
		const { result } = renderHook(() => useTelegramLogin(vi.fn()), { wrapper });
		act(() => result.current.begin());
		await tick(0);
		await tick(1);
		expect(result.current.failure).toBe(gone.message);
		expect(result.current.deepLink).toBeNull();
		await tick(POLL_MS * 3);
		expect(authTelegramPoll).toHaveBeenCalledTimes(1);
	});

	it("keeps asking after a dropped connection", async () => {
		vi.mocked(authTelegramPoll)
			.mockRejectedValueOnce(new ApiError(0, "network.offline", t.apiErrors["network.offline"]))
			.mockResolvedValue({ status: "pending" });
		const { result } = renderHook(() => useTelegramLogin(vi.fn()), { wrapper });
		act(() => result.current.begin());
		await tick(0);
		await tick(POLL_MS);
		expect(authTelegramPoll).toHaveBeenCalledTimes(2);
		expect(result.current.deepLink).not.toBeNull();
	});

	it("resumes a login that was waiting when the page reloaded", async () => {
		sessionStorage.setItem(
			"downtimeless.pending-login",
			JSON.stringify({
				challengeId: 9,
				pollSecret: "s",
				deepLink: started.deep_link,
				expiresAt: Date.now() + 60_000,
			}),
		);
		vi.mocked(authTelegramPoll).mockResolvedValue({ status: "pending" });
		const { result } = renderHook(() => useTelegramLogin(vi.fn()), { wrapper });
		expect(result.current.deepLink).toBe(started.deep_link);
		await tick(0);
		expect(authTelegramPoll).toHaveBeenCalledWith({ challenge_id: 9, poll_secret: "s" });
	});

	it("forgets the attempt when cancelled", async () => {
		vi.mocked(authTelegramPoll).mockResolvedValue({ status: "pending" });
		const { result } = renderHook(() => useTelegramLogin(vi.fn()), { wrapper });
		act(() => result.current.begin());
		await tick(0);
		act(() => result.current.cancel());
		expect(result.current.deepLink).toBeNull();
		expect(sessionStorage.getItem("downtimeless.pending-login")).toBeNull();
	});
});
