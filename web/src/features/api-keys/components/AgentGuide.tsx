import { CopyField, Link, SectionCard } from "@nyxon/nasim";
import { t } from "@/strings";

// What an AI agent or a script needs: the idea, a ready request, and where the schema lives.
export function AgentGuide() {
	const origin = window.location.origin;
	const example = `curl -H "Authorization: Bearer dl_..." ${origin}/api/v1/snapshot`;
	return (
		<SectionCard title={t.apiKeys.aiTitle}>
			<div className="flex flex-col gap-4">
				<p className="text-sm leading-7">{t.apiKeys.aiBody}</p>
				<CopyField label={t.apiKeys.aiExample} value={example} />
				<ul className="flex flex-col gap-2 text-sm">
					<li>
						{t.apiKeys.aiLlms}:{" "}
						<Link href={t.apiKeys.aiLlmsPath} target="_blank">
							<span dir="ltr">{t.apiKeys.aiLlmsPath}</span>
						</Link>
					</li>
					<li>
						{t.apiKeys.aiSchema}:{" "}
						<Link href={t.apiKeys.aiSchemaPath} target="_blank">
							<span dir="ltr">{t.apiKeys.aiSchemaPath}</span>
						</Link>
					</li>
				</ul>
			</div>
		</SectionCard>
	);
}
