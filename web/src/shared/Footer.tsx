import { DEVELOPER_GITHUB_URL, DEVELOPER_TELEGRAM_URL } from "@/shared/links";
import { t } from "@/strings";
import { GithubIcon } from "./GithubIcon";

export function Footer() {
	return (
		<footer className="mt-10 flex flex-wrap items-center justify-center gap-x-3 gap-y-0.5 border-t border-border pt-4 pb-2 text-sm text-muted">
			<span>{t.footer.builtBy}</span>
			<a
				href={DEVELOPER_GITHUB_URL}
				target="_blank"
				rel="noopener noreferrer"
				className="inline-flex items-center gap-1.5 font-medium text-foreground hover:underline"
			>
				<span dir="ltr">{t.footer.name}</span>
				<GithubIcon className="size-4" />
			</a>
			<a
				href={DEVELOPER_TELEGRAM_URL}
				target="_blank"
				rel="noopener noreferrer"
				className="hover:text-foreground hover:underline"
			>
				<span dir="ltr">{t.footer.telegram}</span>
			</a>
		</footer>
	);
}
