import { z } from "zod";
import { t } from "@/strings";

const R = t.register;
// the master checks the same rules; these only save a round trip
export const registerSchema = z
	.object({
		username: z
			.string()
			.trim()
			.toLowerCase()
			.regex(/^[a-z][a-z0-9_.]{2,31}$/, { error: R.usernameInvalid }),
		password: z.string().min(8, { error: R.short }).max(256, { error: R.long }),
		password2: z.string(),
	})
	.superRefine((values, ctx) => {
		if (values.password.trim().toLowerCase() === values.username)
			ctx.addIssue({ code: "custom", path: ["password"], message: R.sameAsUsername });
		if (values.password2 !== values.password)
			ctx.addIssue({ code: "custom", path: ["password2"], message: R.mismatch });
	});
