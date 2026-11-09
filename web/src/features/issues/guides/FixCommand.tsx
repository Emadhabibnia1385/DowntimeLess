import { t } from "@/strings";
import { useGuideIndex } from "./api";
import { Command } from "./GuideBody";

/** The first fix command of a code's guide, to copy beside the issue; the panel never runs it. */
export function FixCommand({ code }: { code: string }) {
	const index = useGuideIndex();
	const cmd = index.data?.playbooks.find((p) => p.code === code)?.fix_cmd_fa;
	if (!cmd) return null;
	return (
		<div className="flex max-w-80 flex-col gap-1">
			<span className="text-xs text-muted">{t.issueGuides.fixCommand}</span>
			<Command cmd={cmd} />
		</div>
	);
}
