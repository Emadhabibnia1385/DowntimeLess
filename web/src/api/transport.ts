// Every request goes through apiFetch: same-origin cookie, JSON, timeout, one ApiError shape.
import { t } from "@/strings";
import { tabWorkspace, WORKSPACE_HEADER } from "./workspace";

export const REQUEST_TIMEOUT_MS = 20_000;

/** A failed request: the master answers `{code, message}`; status 0 means no answer at all. */
export class ApiError extends Error {
	readonly status: number;
	readonly code: string;

	constructor(status: number, code: string, message: string) {
		super(message);
		this.name = "ApiError";
		this.status = status;
		this.code = code;
	}
}

/** What react-query's `error` is for generated hooks. */
export type ErrorType<_Envelope = unknown> = ApiError;

const known = (code: string): string | undefined =>
	(t.apiErrors as Record<string, string | undefined>)[code];

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** The error for a refused answer: our Persian copy for a known code, else the server's words. */
export function fromBody(status: number, body: unknown): ApiError {
	if (isRecord(body) && typeof body.code === "string") {
		const message = typeof body.message === "string" ? body.message : "";
		return new ApiError(status, body.code, known(body.code) ?? (message || t.apiErrors.unknown));
	}
	// FastAPI's own validation answer has no code.
	const code = status >= 500 ? "server.error" : "request.invalid";
	return new ApiError(status, code, known(code) ?? t.apiErrors.unknown);
}

async function readBody(response: Response): Promise<unknown> {
	if (response.status === 204) return undefined;
	const type = response.headers.get("content-type") ?? "";
	return /\bjson\b/i.test(type) ? response.json() : response.text();
}

/** The transport the generated clients call: `apiFetch<Response>(url, init)`. */
export async function apiFetch<T>(url: string, init: RequestInit = {}): Promise<T> {
	const controller = new AbortController();
	const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
	const headers = new Headers(init.headers);
	if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
	const workspace = tabWorkspace();
	if (workspace !== null && !headers.has(WORKSPACE_HEADER))
		headers.set(WORKSPACE_HEADER, String(workspace));
	try {
		const response = await fetch(url, {
			...init,
			headers,
			credentials: "same-origin",
			signal: init.signal ?? controller.signal,
		});
		const body = await readBody(response);
		if (!response.ok) throw fromBody(response.status, body);
		return body as T;
	} catch (error) {
		if (error instanceof ApiError) throw error;
		if (error instanceof SyntaxError) {
			throw new ApiError(502, "server.error", t.apiErrors["server.error"]);
		}
		if (error instanceof DOMException && error.name === "AbortError" && init.signal?.aborted) {
			throw error;
		}
		throw new ApiError(0, "network.offline", t.apiErrors["network.offline"]);
	} finally {
		clearTimeout(timer);
	}
}

export const errorCode = (error: unknown): string | undefined =>
	error instanceof ApiError ? error.code : undefined;

/** A failed request's message in Persian; anything else is the generic line. */
export function errorMessage(error: unknown): string {
	return error instanceof ApiError && error.message ? error.message : t.apiErrors.unknown;
}
