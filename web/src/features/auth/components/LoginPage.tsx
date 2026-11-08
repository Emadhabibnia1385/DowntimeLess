import { zodResolver } from "@hookform/resolvers/zod";
import {
	Button,
	CopyField,
	FormRoot,
	LinkButton,
	Notice,
	Spinner,
	SubmitButton,
	TextField,
	useTheme,
} from "@nyxon/nasim";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { authTelegramWebapp, useAuthLogin } from "@/api/generated/auth/auth";
import type { UserOut } from "@/api/generated/model";
import { errorMessage } from "@/api/transport";
import { brandLogo } from "@/shared/brand";
import { Footer } from "@/shared/Footer";
import { TelegramIcon } from "@/shared/icons";
import { QRCode } from "@/shared/QRCode";
import { useDocumentTitle } from "@/shared/useDocumentTitle";
import { t } from "@/strings";
import { miniAppInitData } from "../miniApp";
import { safeRedirect } from "../pending";
import { useStartSession } from "../session";
import { useOnceDone } from "../useOnceDone";
import { useTelegramLogin } from "../useTelegramLogin";

const schema = z.object({
	username: z.string().trim().min(1, { error: t.login.needBoth }),
	password: z.string().min(1, { error: t.login.needBoth }),
});
type Values = z.input<typeof schema>;

function Divider() {
	return (
		<div className="flex items-center gap-3 text-xs text-muted">
			<span className="h-px flex-1 bg-border" />
			<span>{t.login.or}</span>
			<span className="h-px flex-1 bg-border" />
		</div>
	);
}

// A Mini App signs in at once from its launch data; the query makes StrictMode ask only once.
function useMiniAppLogin(onDone: (user: UserOut) => void) {
	const initData = miniAppInitData();
	const query = useQuery({
		queryKey: ["telegram-webapp"],
		queryFn: () => authTelegramWebapp({ init_data: initData ?? "" }),
		enabled: initData !== null,
		retry: false,
		staleTime: Number.POSITIVE_INFINITY,
	});
	useOnceDone(query.data, onDone);
	return { isLoading: initData !== null && query.isPending, error: query.error };
}

// Two ways in: Telegram vouches for the person, or a username and password.
export function LoginPage({ redirect }: { redirect: string | undefined }) {
	useDocumentTitle(t.login.title);
	const navigate = useNavigate();
	const startSession = useStartSession();
	const done = (user: UserOut) => {
		startSession(user);
		void navigate({ to: safeRedirect(redirect), replace: true });
	};
	const telegram = useTelegramLogin(done);
	const miniApp = useMiniAppLogin(done);
	const login = useAuthLogin({ mutation: { onSuccess: done } });
	const form = useForm<Values>({
		resolver: zodResolver(schema),
		defaultValues: { username: "", password: "" },
	});
	const problem = telegram.failure ?? (miniApp.error ? errorMessage(miniApp.error) : null);
	const link = telegram.deepLink;
	const { scheme } = useTheme();

	return (
		<div className="grid min-h-dvh place-items-center bg-background px-page py-10 text-foreground">
			<div className="flex w-full max-w-sm flex-col gap-6">
				<div className="flex flex-col items-center gap-2 text-center">
					<h1>
						<img
							src={brandLogo(scheme)}
							alt={t.brand.logoAlt}
							width={1200}
							height={339}
							className="mx-auto h-auto w-72 max-w-full"
						/>
					</h1>
					<p className="text-sm text-muted">{t.login.lead}</p>
				</div>

				{problem ? (
					<Notice tone="danger" role="alert">
						{problem}
					</Notice>
				) : null}

				<div className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-5">
					{miniApp.isLoading ? (
						<div className="flex items-center justify-center gap-2 text-sm">
							<Spinner size="sm" />
							{t.login.miniApp}
						</div>
					) : link ? (
						<div className="flex flex-col items-center gap-4 text-center">
							<div className="flex items-center gap-2 font-medium">
								<Spinner size="sm" />
								{t.login.waitingTitle}
							</div>
							<p className="text-sm text-muted">{t.login.waiting}</p>
							<LinkButton href={link} target="_blank" size="lg" fullWidth>
								<TelegramIcon aria-hidden />
								{t.login.openInTelegram}
							</LinkButton>
							<QRCode value={link} label={t.login.qrLabel} />
							<p className="text-xs text-muted">{t.login.scan}</p>
							<div className="w-full min-w-0">
								<CopyField label={t.login.linkLabel} value={link} />
							</div>
							<Button variant="ghost" onPress={telegram.cancel}>
								{t.login.cancel}
							</Button>
						</div>
					) : (
						<Button size="lg" fullWidth isPending={telegram.isStarting} onPress={telegram.begin}>
							<TelegramIcon aria-hidden />
							{telegram.isStarting ? t.login.opening : t.login.telegram}
						</Button>
					)}

					<Divider />

					<FormRoot
						form={form}
						className="flex flex-col gap-3 text-start"
						onSubmit={(values) =>
							login.mutate({
								data: { username: values.username.trim(), password: values.password },
							})
						}
					>
						<TextField
							name="username"
							dir="ltr"
							label={t.login.username}
							autoComplete="username"
							spellCheck={false}
						/>
						<TextField
							name="password"
							dir="ltr"
							type="password"
							label={t.login.password}
							autoComplete="current-password"
						/>
						{login.error ? (
							<Notice tone="danger" role="alert">
								{errorMessage(login.error)}
							</Notice>
						) : null}
						<SubmitButton>{t.login.submit}</SubmitButton>
					</FormRoot>
				</div>
				<div className="flex justify-center">
					<Footer />
				</div>
			</div>
		</div>
	);
}
