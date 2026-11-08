import { useTheme } from "@nyxon/nasim";
import { brandMark } from "@/shared/brand";
import { GithubIcon } from "@/shared/GithubIcon";
import { PROJECT_GITHUB_URL } from "@/shared/links";
import { t } from "@/strings";

// The sidebar's top block: shield mark, project name, the slogan, and the project's GitHub circle.
export function Brand() {
	const { scheme } = useTheme();
	return (
		<span className="flex w-full items-center justify-between gap-3">
			<span className="flex items-center gap-3">
				<img
					src={brandMark(scheme)}
					alt=""
					aria-hidden
					width={44}
					height={44}
					className="size-11 shrink-0"
				/>
				<span className="flex flex-col leading-tight">
					<span className="text-lg font-bold">{t.brand.name}</span>
					<span className="text-xs text-muted">{t.brand.tagline}</span>
				</span>
			</span>
			<a
				href={PROJECT_GITHUB_URL}
				target="_blank"
				rel="noopener noreferrer"
				aria-label={t.brand.githubLabel}
				title={t.brand.githubLabel}
				className="grid size-10 shrink-0 place-items-center rounded-full text-muted transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-accent"
			>
				<GithubIcon className="size-6" />
			</a>
		</span>
	);
}
