import { tv } from "tailwind-variants";
import { DEVELOPER_GITHUB_URL, DEVELOPER_TELEGRAM_URL } from "@/shared/links";
import { t } from "@/strings";
import { GithubIcon } from "./GithubIcon";

const footer = tv({
	base: "fixed inset-x-0 bottom-[var(--nasim-bottom-bar,0px)] z-20 flex flex-wrap items-center justify-center gap-x-3 gap-y-0.5 border-t border-border bg-surface px-safe py-2 text-sm text-muted",
	variants: { sidebar: { true: "lg:start-64" } },
});

// Pinned to the bottom of every screen: "built by" with the developer's GitHub and Telegram.
export function Footer({ sidebar = false }: { sidebar?: boolean }) {
	return (
		<footer className={footer({ sidebar })}>
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
