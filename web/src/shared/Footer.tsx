import { Link } from "@nyxon/nasim";
import { DEVELOPER_GITHUB_URL, DEVELOPER_TELEGRAM_URL } from "@/shared/links";
import { t } from "@/strings";

// The attribution line: developer name and handle linking to Telegram, and the GitHub profile.
export function Footer() {
	return (
		<p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted">
			<span>{t.footer.developer}</span>
			<Link href={DEVELOPER_TELEGRAM_URL} target="_blank" rel="noopener noreferrer">
				<span dir="ltr">{t.footer.telegram}</span>
			</Link>
			<Link href={DEVELOPER_GITHUB_URL} target="_blank" rel="noopener noreferrer">
				{t.footer.github}
			</Link>
		</p>
	);
}
