import { describe, expect, it } from "vitest";
import { t } from "@/strings";
import { miniAppInitData } from "./miniApp";
import {
	outcomeOf,
	type PendingLogin,
	pendingFrom,
	readPending,
	safeRedirect,
	writePending,
} from "./pending";

const NOW = 1_000_000;
const pending: PendingLogin = {
	challengeId: 7,
	pollSecret: "secret",
	deepLink: "https://t.me/bot?start=wl_abc",
	expiresAt: NOW + 300_000,
};
const user = {
	id: 1,
	name: "Emad",
	username: null,
	role: "owner",
	has_password: false,
	workspace: { id: 1, name: "فضای کار اصلی", role: "owner", is_personal: true },
	tg_username: null,
};

function memoryStore() {
	const data = new Map<string, string>();
	return {
		getItem: (key: string) => data.get(key) ?? null,
		setItem: (key: string, value: string) => void data.set(key, value),
		removeItem: (key: string) => void data.delete(key),
	};
}

describe("pendingFrom", () => {
	it("turns the server's seconds into a browser deadline", () => {
		const made = pendingFrom(
			{ challenge_id: 7, deep_link: pending.deepLink, expires_in: 300, poll_secret: "secret" },
			NOW,
		);
		expect(made).toEqual(pending);
	});
});

describe("the stored login", () => {
	it("comes back after a reload", () => {
		const store = memoryStore();
		writePending(pending, store);
		expect(readPending(NOW + 1000, store)).toEqual(pending);
	});

	it("is dropped once its deadline has passed", () => {
		const store = memoryStore();
		writePending(pending, store);
		expect(readPending(pending.expiresAt + 1, store)).toBeNull();
	});

	it("is forgotten on request and survives garbage", () => {
		const store = memoryStore();
		writePending(pending, store);
		writePending(null, store);
		expect(readPending(NOW, store)).toBeNull();
		store.setItem("downtimeless.pending-login", "{not json");
		expect(readPending(NOW, store)).toBeNull();
	});
});

describe("outcomeOf", () => {
	it("keeps waiting while the master says pending", () => {
		expect(outcomeOf({ status: "pending" }, pending, NOW)).toEqual({ kind: "wait" });
	});

	it("hands over the user once approved", () => {
		expect(outcomeOf({ status: "approved", user }, pending, NOW)).toEqual({
			kind: "approved",
			user,
		});
	});

	it("does not treat approval without a user as a sign-in", () => {
		expect(outcomeOf({ status: "approved", user: null }, pending, NOW)).toEqual({ kind: "wait" });
	});

	it("explains a refusal in Persian", () => {
		expect(outcomeOf({ status: "denied" }, pending, NOW)).toEqual({
			kind: "failed",
			message: t.login.denied,
		});
	});

	it("ends the attempt on expiry, from the master or from the local deadline", () => {
		const expired = { kind: "failed", message: t.login.expired };
		expect(outcomeOf({ status: "expired" }, pending, NOW)).toEqual(expired);
		expect(outcomeOf({ status: "pending" }, pending, pending.expiresAt + 1)).toEqual(expired);
	});
});

describe("safeRedirect", () => {
	it("follows a path on this site", () => {
		expect(safeRedirect("/servers/3?range=7d")).toBe("/servers/3?range=7d");
	});

	it("never leaves the site or loops back to the login page", () => {
		expect(safeRedirect("https://evil.example/")).toBe("/");
		expect(safeRedirect("//evil.example/")).toBe("/");
		expect(safeRedirect("/login?redirect=/")).toBe("/");
		expect(safeRedirect(undefined)).toBe("/");
	});
});

describe("miniAppInitData", () => {
	it("reads the launch data from the address hash", () => {
		expect(miniAppInitData("#tgWebAppData=query_id%3DAA&tgWebAppVersion=8")).toBe("query_id=AA");
	});

	it("is null outside a Mini App", () => {
		expect(miniAppInitData("")).toBeNull();
		expect(miniAppInitData("#other=1")).toBeNull();
	});
});
