import { CopyField, SectionCard } from "@nyxon/nasim";
import { t } from "@/strings";

// What an AI agent or a script needs: three short steps and one ready request.
export function AgentGuide() {
	const example = `curl -H "Authorization: Bearer dl_..." ${window.location.origin}/api/v1/snapshot`;
	return (
		<SectionCard title={t.apiKeys.aiTitle}>
			<div className="flex flex-col gap-4">
				<ol className="flex list-decimal flex-col gap-1 ps-5 text-sm leading-7">
					<li>{t.apiKeys.aiStep1}</li>
					<li>{t.apiKeys.aiStep2}</li>
					<li>{t.apiKeys.aiStep3}</li>
				</ol>
				<CopyField label={t.apiKeys.aiExample} value={example} />
			</div>
		</SectionCard>
	);
}
