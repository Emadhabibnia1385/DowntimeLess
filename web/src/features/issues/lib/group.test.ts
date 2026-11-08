import { describe, expect, it } from "vitest";
import type { Issue } from "@/api/generated/model";
import { familyOf, groupIssues, valueOf } from "./group";

const issue = (over: Partial<Issue>): Issue => ({
	id: "x",
	server_id: 1,
	server_name: "de-1",
	code: "steal",
	severity: "warning",
	title: "steal بالا",
	suggestion: "تیکت بدهید",
	evidence: {},
	...over,
});

describe("familyOf", () => {
	it("keeps the part before a colon", () => {
		expect(familyOf("ping:1.2.3.4")).toBe("ping");
		expect(familyOf("ssl_expiry")).toBe("ssl_expiry");
	});
});

describe("valueOf", () => {
	it("shows the measured percent, the units, the days left and the relays", () => {
		expect(valueOf(issue({ evidence: { steal_pct: 12.8 } }))).toContain("۱۲");
		expect(
			valueOf(issue({ code: "failed_units", evidence: { units: ["a.service", "b.service"] } })),
		).toBe("a.service, b.service");
		expect(valueOf(issue({ code: "ssl_expiry", evidence: { name: "x.com", days_left: -3 } }))).toBe(
			"x.com: منقضی شده",
		);
		expect(
			valueOf(issue({ code: "ssl_expiry", evidence: { name: "x.com", days_left: 5 } })),
		).toContain("۵ روز");
		expect(
			valueOf(issue({ code: "ping:1.1.1.1", evidence: { loss_pct: 40, relays: ["a", "b"] } })),
		).toContain("۲ رله");
		expect(valueOf(issue({ code: "reboot_required" }))).toBe("");
	});
});

describe("groupIssues", () => {
	const groups = groupIssues([
		issue({ id: "1", server_name: "a", evidence: { steal_pct: 10 } }),
		issue({ id: "2", server_name: "b", evidence: { steal_pct: 30 } }),
		issue({
			id: "3",
			code: "offline",
			severity: "critical",
			server_name: "c",
			evidence: { last_seen_s_ago: 600 },
		}),
		issue({
			id: "4",
			code: "ssl_expiry",
			severity: "critical",
			server_id: null,
			server_name: "SSL",
			evidence: { name: "z.com", days_left: 2 },
		}),
	]);

	it("makes one row per kind of problem with every server listed in it", () => {
		const steal = groups.find((g) => g.family === "steal");
		expect(steal?.items.map((i) => i.serverName)).toEqual(["a", "b"]);
		expect(steal?.title).toBe("استیل بالا (میزبان مجازی شلوغ)");
	});

	it("puts critical kinds before warnings and sends certificate rows to the SSL page", () => {
		expect(groups.map((g) => g.severity)).toEqual(["critical", "critical", "warning"]);
		expect(groups.find((g) => g.family === "ssl_expiry")?.items[0].to).toBe("ssl");
		expect(groups.find((g) => g.family === "offline")?.items[0].to).toBe("server");
	});
});
