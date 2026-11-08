import { useTheme } from "@nyxon/nasim";
import { brandMark } from "@/shared/brand";
import { GithubIcon } from "@/shared/GithubIcon";
import { PROJECT_GITHUB_URL } from "@/shared/links";
import { t } from "@/strings";

// One node serves the sidebar, the phone top bar and its menu; `in-[...]` styles each place.
export function Brand() {
	const { scheme } = useTheme();
	return (
		<span className="flex w-full items-center justify-between gap-3 in-[header]:contents in-[[role=dialog]]:pb-6">
			<span className="flex items-center gap-3 in-[header]:absolute in-[header]:inset-x-0 in-[header]:top-1/2 in-[header]:mx-auto in-[header]:w-fit in-[header]:-translate-y-1/2">
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
				className="grid size-10 shrink-0 place-items-center rounded-full text-muted transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-accent in-[header]:absolute in-[header]:end-3 in-[header]:top-1/2 in-[header]:-translate-y-1/2 in-[header]:sm:hidden in-[[role=dialog]]:translate-y-6"
			>
				<GithubIcon className="size-6" />
			</a>
		</span>
	);
}
