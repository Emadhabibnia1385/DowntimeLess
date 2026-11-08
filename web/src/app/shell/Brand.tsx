import { ThemeToggle, useTheme } from "@nyxon/nasim";
import { brandLogo } from "@/shared/brand";
import { GithubIcon } from "@/shared/GithubIcon";
import { PROJECT_GITHUB_URL } from "@/shared/links";
import { t } from "@/strings";

// The logo and GitHub; the phone top bar swaps GitHub for the theme toggle.
export function Brand() {
	const { scheme } = useTheme();
	return (
		<span className="flex w-full items-center justify-between gap-3 in-[header]:contents in-[[role=dialog]]:pb-6">
			<span className="flex flex-col items-start gap-0.5 in-[header]:absolute in-[header]:inset-x-0 in-[header]:top-1/2 in-[header]:mx-auto in-[header]:w-fit in-[header]:-translate-y-1/2 in-[header]:items-center">
				<img
					src={brandLogo(scheme)}
					alt={t.brand.logoAlt}
					width={1200}
					height={339}
					className="h-12 w-auto in-[header]:h-10"
				/>
			</span>
			<a
				href={PROJECT_GITHUB_URL}
				target="_blank"
				rel="noopener noreferrer"
				aria-label={t.brand.githubLabel}
				title={t.brand.githubLabel}
				className="grid size-10 shrink-0 place-items-center rounded-full text-muted transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-accent in-[header]:hidden in-[[role=dialog]]:translate-y-6"
			>
				<GithubIcon className="size-6" />
			</a>
			<span className="hidden in-[header]:absolute in-[header]:end-3 in-[header]:top-1/2 in-[header]:block in-[header]:-translate-y-1/2 in-[header]:sm:hidden">
				<ThemeToggle lightLabel={t.theme.light} darkLabel={t.theme.dark} />
			</span>
		</span>
	);
}
