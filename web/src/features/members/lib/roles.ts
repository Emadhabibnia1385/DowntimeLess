import { z } from "zod";
import { t } from "@/strings";

/** What the owner may give; one owner per workspace, so owner is not on the list. */
export const ASSIGNABLE = ["viewer", "operator", "admin"] as const;
export type Assignable = (typeof ASSIGNABLE)[number];

export const ROLE_OPTIONS = ASSIGNABLE.map((role) => ({
	value: role,
	label: t.members.roles[role],
	description: t.members.roleHints[role],
}));

export function isAssignable(role: string): role is Assignable {
	return (ASSIGNABLE as readonly string[]).includes(role);
}

const DIGIT_SETS = ["۰۱۲۳۴۵۶۷۸۹", "٠١٢٣٤٥٦٧٨٩"];

/** Telegram ids typed with Persian or Arabic digits are the same number. */
export function latinDigits(value: string): string {
	return value.replace(/[۰-۹٠-٩]/g, (digit) => {
		const set = DIGIT_SETS.find((digits) => digits.includes(digit)) ?? "";
		return String(set.indexOf(digit));
	});
}

export type WhoKind = "telegram" | "invite" | "account";
export type Who = { kind: WhoKind; value: string };

const TG_ID = /^[1-9]\d{0,14}$/;
const TG_USERNAME = /^@([A-Za-z][A-Za-z0-9_]{4,31})$/;
const ACCOUNT = /^[^\s@]{3,64}$/;

/** What the owner typed: a Telegram id, a @username (invite) or a panel account username. */
export function parseWho(raw: string): Who | null {
	const value = latinDigits(raw.trim());
	if (TG_ID.test(value)) return { kind: "telegram", value };
	const handle = TG_USERNAME.exec(value);
	if (handle) return { kind: "invite", value: handle[1] };
	if (/^\d/.test(value) || value.startsWith("@")) return null;
	return ACCOUNT.test(value) ? { kind: "account", value: value.toLowerCase() } : null;
}

export const addSchema = z
	.object({
		who: z.string().trim().min(1, { error: t.members.whoRequired }),
		name: z.string().trim().max(64, { error: t.members.nameLong }),
		role: z.enum(ASSIGNABLE),
	})
	.superRefine((values, ctx) => {
		const who = parseWho(values.who);
		if (!who) ctx.addIssue({ code: "custom", path: ["who"], message: t.members.whoInvalid });
		else if (who.kind === "invite" && values.role === "admin")
			ctx.addIssue({ code: "custom", path: ["role"], message: t.members.inviteAdmin });
	});
export type AddValues = z.input<typeof addSchema>;
