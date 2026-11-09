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

describe("the Phase 1 detectors", () => {
	it("groups each new kind under its own Persian title", () => {
		const codes = [
			"rebooted",
			"ip_changed",
			"resized",
			"blacklisted",
			"relay_egress",
			"relay_filtered",
		];
		const groups = groupIssues(
			[...codes, "load_per_core", "quota", "quota_pair"].map((code) => issue({ id: code, code })),
		);
		expect(groups.map((group) => group.title)).not.toContain("steal بالا");
		expect(new Set(groups.map((group) => group.family)).size).toBe(9);
		expect(groups.find((group) => group.family === "quota")?.title).toBe("حجم ماهانه رو به پایان");
	});

	it("shows the days left of a quota and the new address of a changed IP", () => {
		expect(valueOf(issue({ code: "quota", evidence: { days_left: 1.5 } }))).toContain("روز");
		expect(valueOf(issue({ code: "ip_changed", evidence: { new_ip: "203.0.113.7" } }))).toBe(
			"203.0.113.7",
		);
	});
});

describe("phase 2 and 3 issues", () => {
	it("shows the ports, the reseller share and the node, and names the group in Persian", () => {
		expect(
			valueOf(issue({ code: "listener_missing", evidence: { ports: ["tcp/443", "tcp/22"] } })),
		).toBe("tcp/443, tcp/22");
		expect(
			valueOf(issue({ code: "reseller_quota:r1", evidence: { reseller: "r1", used_pct: 97 } })),
		).toContain("r1: ");
		expect(valueOf(issue({ code: "node_silent:5", evidence: { node: "node-05" } }))).toBe(
			"node-05",
		);
		const [group] = groupIssues([
			issue({ code: "node_down:5", server_id: 9, server_name: "panel" }),
		]);
		expect(group.title).toBe("نود در پنل وصل نیست");
		expect(group.items[0].to).toBe("panel");
	});
});

describe("forward issues", () => {
	it("groups each relay forward under one Persian title and shows the ports", () => {
		const groups = groupIssues([
			issue({ id: "a", code: "relay_forward_broken:3:21001", evidence: { ports: ["tcp/21001"] } }),
			issue({
				id: "b",
				code: "relay_forward_broken:4:all",
				evidence: { ports: ["tcp/21001", "tcp/21002"] },
			}),
			issue({ id: "c", code: "dnat_dead_target", evidence: { ports: ["tcp/21005"] } }),
		]);
		const forward = groups.find((g) => g.family === "relay_forward_broken");
		expect(forward?.title).toBe("فوروارد لوکیشن روی رله خراب");
		expect(forward?.items.map((i) => i.value)).toEqual(["tcp/21001", "tcp/21001, tcp/21002"]);
		expect(groups.find((g) => g.family === "dnat_dead_target")?.title).toBe(
			"قانون DNAT به مقصد مرده",
		);
	});
});
