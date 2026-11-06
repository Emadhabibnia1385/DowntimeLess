import { afterEach, describe, expect, it, vi } from "vitest";
import { t } from "@/strings";
import { ApiError, apiFetch, errorMessage, fromBody } from "./transport";

const reply = (status: number, body?: unknown) =>
	new Response(body === undefined ? null : JSON.stringify(body), {
		status,
		headers: body === undefined ? {} : { "content-type": "application/json" },
	});

afterEach(() => vi.unstubAllGlobals());

describe("fromBody", () => {
	it("maps a known code to our Persian message", () => {
		const error = fromBody(401, { code: "auth.invalid", message: "anything" });
		expect(error).toBeInstanceOf(ApiError);
		expect(error.code).toBe("auth.invalid");
		expect(error.status).toBe(401);
		expect(error.message).toBe(t.apiErrors["auth.invalid"]);
	});

	it("uses the server's message for a code it does not know", () => {
		expect(fromBody(409, { code: "new.thing", message: "پیام سرور" }).message).toBe("پیام سرور");
	});

	it("handles FastAPI's validation answer, which has no code", () => {
		const error = fromBody(422, { detail: [{ loc: ["body"], msg: "x", type: "y" }] });
		expect(error.code).toBe("request.invalid");
		expect(error.message).toBe(t.apiErrors["request.invalid"]);
	});

	it("treats a 5xx without a body as a server error", () => {
		expect(fromBody(502, "<html>").code).toBe("server.error");
	});
});

describe("apiFetch", () => {
	it("sends the cookie to our own origin as JSON and returns the body", async () => {
		const fetchMock = vi.fn().mockResolvedValue(reply(200, { ok: true }));
		vi.stubGlobal("fetch", fetchMock);
		await expect(apiFetch("/api/v1/health")).resolves.toEqual({ ok: true });
		const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
		expect(init.credentials).toBe("same-origin");
		expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
	});

	it("resolves a 204 with nothing", async () => {
		vi.stubGlobal("fetch", vi.fn().mockResolvedValue(reply(204)));
		await expect(apiFetch("/api/v1/auth/logout", { method: "POST" })).resolves.toBeUndefined();
	});

	it("throws the master's error with its code", async () => {
		vi.stubGlobal(
			"fetch",
			vi.fn().mockResolvedValue(reply(404, { code: "server.not_found", message: "x" })),
		);
		await expect(apiFetch("/api/v1/servers/9")).rejects.toMatchObject({
			status: 404,
			code: "server.not_found",
			message: t.apiErrors["server.not_found"],
		});
	});

	it("reports no connection as status 0", async () => {
		vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
		await expect(apiFetch("/api/v1/servers")).rejects.toMatchObject({
			status: 0,
			code: "network.offline",
		});
	});
});

describe("errorMessage", () => {
	it("is the error's Persian message, or a generic line for anything else", () => {
		expect(errorMessage(new ApiError(403, "auth.forbidden", "دسترسی کافی ندارید."))).toBe(
			"دسترسی کافی ندارید.",
		);
		expect(errorMessage(new Error("boom"))).toBe(t.apiErrors.unknown);
	});
});
