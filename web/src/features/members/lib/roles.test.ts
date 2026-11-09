import { describe, expect, it } from "vitest";
import { addSchema, isAssignable, latinDigits, parseWho } from "./roles";

describe("member roles and the add form", () => {
	it("never offers the owner role", () => {
		expect(isAssignable("owner")).toBe(false);
		expect(isAssignable("operator")).toBe(true);
	});

	it("reads Persian and Arabic digits as Latin", () => {
		expect(latinDigits("۱۲۳۴۵۶۷۸۹۰")).toBe("1234567890");
		expect(latinDigits("٤٥٦")).toBe("456");
	});

	it("tells a Telegram id, a Telegram @username and an account username apart", () => {
		expect(parseWho(" ۱۲۳۴۵۶۷۸۹ ")).toEqual({ kind: "telegram", value: "123456789" });
		expect(parseWho("@Some_User")).toEqual({ kind: "invite", value: "Some_User" });
		expect(parseWho("Sara.K")).toEqual({ kind: "account", value: "sara.k" });
		for (const bad of [
			"",
			"@ab",
			"@1abcde",
			"0123",
			"1234567890123456",
			"12a4",
			"-5",
			"a b",
			"ab",
		]) {
			expect(parseWho(bad)).toBeNull();
		}
	});

	it("refuses an admin invite by @username", () => {
		expect(addSchema.safeParse({ who: "@some_user", name: "", role: "admin" }).success).toBe(false);
		expect(addSchema.safeParse({ who: "@some_user", name: "", role: "operator" }).success).toBe(
			true,
		);
		expect(addSchema.safeParse({ who: "123456789", name: "", role: "admin" }).success).toBe(true);
	});
});
