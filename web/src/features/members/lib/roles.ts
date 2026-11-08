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

export const addSchema = z.object({
	tgId: z
		.string()
		.transform((value) => latinDigits(value.trim()))
		.pipe(
			z
				.string()
				.min(1, { error: t.members.tgIdRequired })
				.regex(/^[1-9]\d{0,14}$/, { error: t.members.tgIdDigits }),
		),
	name: z.string().trim().max(64, { error: t.members.nameLong }),
	role: z.enum(ASSIGNABLE),
});
export type AddValues = z.input<typeof addSchema>;
