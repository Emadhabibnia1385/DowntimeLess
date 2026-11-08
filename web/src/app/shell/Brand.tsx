import { useTheme } from "@nyxon/nasim";
import { brandMark } from "@/shared/brand";
import { t } from "@/strings";

// The sidebar's top block: shield mark, project name and the small tagline.
export function Brand() {
	const { scheme } = useTheme();
	return (
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
	);
}
