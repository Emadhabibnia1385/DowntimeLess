import { zodResolver } from "@hookform/resolvers/zod";
import { FormRoot, Notice, SubmitButton, TextField } from "@nyxon/nasim";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import { useAuthRegister } from "@/api/generated/auth/auth";
import type { UserOut } from "@/api/generated/model";
import { errorMessage } from "@/api/transport";
import { t } from "@/strings";
import { registerSchema } from "../register";

const R = t.register;
type Values = z.input<typeof registerSchema>;

// A username and a password typed twice; the new account signs in at once into its own workspace.
export function RegisterForm({ onDone }: { onDone: (user: UserOut) => void }) {
	const register = useAuthRegister({ mutation: { onSuccess: onDone } });
	const form = useForm<Values>({
		resolver: zodResolver(registerSchema),
		defaultValues: { username: "", password: "", password2: "" },
	});
	return (
		<FormRoot
			form={form}
			className="flex flex-col gap-3 text-start"
			onSubmit={(values) => {
				const parsed = registerSchema.parse(values);
				register.mutate({ data: parsed });
			}}
		>
			<h2 className="text-lg font-semibold">{R.title}</h2>
			<p className="text-sm leading-6 text-muted">{R.lead}</p>
			<TextField
				name="username"
				dir="ltr"
				label={R.username}
				description={R.usernameHint}
				autoComplete="username"
				spellCheck={false}
				maxLength={32}
			/>
			<TextField
				name="password"
				dir="ltr"
				type="password"
				label={R.password}
				description={R.passwordHint}
				autoComplete="new-password"
				maxLength={256}
			/>
			<TextField
				name="password2"
				dir="ltr"
				type="password"
				label={R.password2}
				autoComplete="new-password"
				maxLength={256}
			/>
			{register.error ? (
				<Notice tone="danger" role="alert">
					{errorMessage(register.error)}
				</Notice>
			) : null}
			<SubmitButton>{R.submit}</SubmitButton>
		</FormRoot>
	);
}
