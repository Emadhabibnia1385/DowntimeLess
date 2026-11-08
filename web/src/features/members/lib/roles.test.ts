import { describe, expect, it } from "vitest";
import { addSchema, isAssignable, latinDigits } from "./roles";

describe("member roles and the add form", () => {
	it("never offers the owner role", () => {
		expect(isAssignable("owner")).toBe(false);
		expect(isAssignable("operator")).toBe(true);
	});

	it("reads Persian and Arabic digits as Latin", () => {
		expect(latinDigits("۱۲۳۴۵۶۷۸۹۰")).toBe("1234567890");
		expect(latinDigits("٤٥٦")).toBe("456");
	});

	it("accepts a numeric id only", () => {
		const ok = addSchema.safeParse({ tgId: " ۱۲۳۴۵۶۷۸۹ ", name: "", role: "admin" });
		expect(ok.success && ok.data.tgId).toBe("123456789");
		for (const bad of ["", "abc", "12a4", "-5", "0123", "1234567890123456"]) {
			expect(addSchema.safeParse({ tgId: bad, name: "", role: "viewer" }).success).toBe(false);
		}
	});
});
