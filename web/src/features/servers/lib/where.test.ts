import { describe, expect, it } from "vitest";
import { whereOf } from "./where";

const reported = { country: "DE", city: "Frankfurt am Main", org: "PCCWG INTERNAL" };

describe("whereOf", () => {
	it("shows an Iran relay as Iran whatever address it reports", () => {
		expect(whereOf({ role: "relay", ...reported })).toEqual({ flag: "🇮🇷", place: "Iran" });
	});
	it("shows a relay's real city and provider once its agent places it in Iran", () => {
		const w = whereOf({ role: "relay", country: "IR", city: "Tehran", org: "Atrin Information" });
		expect(w.flag).toBe("🇮🇷");
		expect(w.place).toContain("Tehran");
	});
	it("shows any other server where its report says", () => {
		const w = whereOf({
			role: "exit",
			country: "DE",
			city: "Falkenstein",
			org: "Hetzner Online GmbH",
		});
		expect(w.flag).toBe("🇩🇪");
		expect(w.place).toContain("Germany");
		expect(w.place).toContain("Falkenstein");
	});
});
