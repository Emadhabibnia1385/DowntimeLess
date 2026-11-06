import { zodResolver } from "@hookform/resolvers/zod";
import { FormRoot, Notice, SubmitButton, TextField, toast } from "@nyxon/nasim";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuthSetPassword } from "@/api/generated/auth/auth";
import type { UserOut } from "@/api/generated/model";
import { errorMessage } from "@/api/transport";
import { useStartSession } from "@/features/auth";
import { t } from "@/strings";

const MIN_PASSWORD = 8;

const schema = z
	.object({
		username: z.string().trim().min(1, { error: t.account.usernameRequired }),
		currentPassword: z.string(),
		password: z.string().min(MIN_PASSWORD, { error: t.account.short }),
		confirm: z.string(),
	})
	.refine((values) => values.password === values.confirm, {
		error: t.account.mismatch,
		path: ["confirm"],
	});
const schemaWithCurrent = schema.refine((values) => values.currentPassword !== "", {
	error: t.account.currentRequired,
	path: ["currentPassword"],
});
type Values = z.input<typeof schema>;

// Sets or changes the website password; a person who already has one must prove it first.
export function PasswordForm({ user }: { user: UserOut }) {
	const startSession = useStartSession();
	const save = useAuthSetPassword({
		mutation: {
			onSuccess: (updated) => {
				startSession(updated);
				form.reset({ ...form.getValues(), currentPassword: "", password: "", confirm: "" });
				toast.success(t.common.saved);
			},
		},
	});
	const form = useForm<Values>({
		resolver: zodResolver(user.has_password ? schemaWithCurrent : schema),
		defaultValues: {
			username: user.username ?? "",
			currentPassword: "",
			password: "",
			confirm: "",
		},
	});
	return (
		<FormRoot
			form={form}
			className="flex max-w-md flex-col gap-4"
			onSubmit={(values) =>
				save.mutate({
					data: {
						username: values.username.trim(),
						password: values.password,
						current_password: user.has_password ? values.currentPassword : null,
					},
				})
			}
		>
			<p className="text-sm text-muted">{t.account.passwordHint}</p>
			<TextField
				name="username"
				dir="ltr"
				label={t.account.newUsername}
				autoComplete="username"
				spellCheck={false}
			/>
			{user.has_password ? (
				<TextField
					name="currentPassword"
					dir="ltr"
					type="password"
					label={t.account.currentPassword}
					autoComplete="current-password"
				/>
			) : null}
			<TextField
				name="password"
				dir="ltr"
				type="password"
				label={t.account.newPassword}
				autoComplete="new-password"
			/>
			<TextField
				name="confirm"
				dir="ltr"
				type="password"
				label={t.account.confirmPassword}
				autoComplete="new-password"
			/>
			{save.error ? (
				<Notice tone="danger" role="alert">
					{errorMessage(save.error)}
				</Notice>
			) : null}
			<SubmitButton>{t.account.submit}</SubmitButton>
		</FormRoot>
	);
}
