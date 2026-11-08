import { CopyButton, SectionCard, StaticTable } from "@nyxon/nasim";
import { t } from "@/strings";

type Item = { id: string; label: string; hint: string; value: string };

// Every address an assistant or script needs, as a table row with its own copy button.
export function AgentGuide() {
	const origin = window.location.origin;
	const items: Item[] = [
		{
			id: "llms",
			label: t.apiKeys.llmsLabel,
			hint: t.apiKeys.llmsHint,
			value: `${origin}${t.apiKeys.llmsPath}`,
		},
		{
			id: "schema",
			label: t.apiKeys.schemaLabel,
			hint: t.apiKeys.schemaHint,
			value: `${origin}${t.apiKeys.schemaPath}`,
		},
		{
			id: "example",
			label: t.apiKeys.aiExample,
			hint: t.apiKeys.aiExampleHint,
			value: `curl -H "Authorization: Bearer dl_..." ${origin}/api/v1/snapshot`,
		},
	];
	return (
		<SectionCard title={t.apiKeys.aiTitle}>
			<StaticTable
				caption={t.apiKeys.aiTitle}
				className="min-w-[30rem]"
				columns={[t.apiKeys.aiColItem, t.apiKeys.aiColCopy, t.apiKeys.aiColAddress]}
				rows={items.map((item) => ({
					id: item.id,
					cells: [
						<div key="item" className="flex flex-col gap-0.5">
							<span className="font-semibold">{item.label}</span>
							<span className="text-xs font-normal text-muted">{item.hint}</span>
						</div>,
						<CopyButton
							key="copy"
							value={item.value}
							label={t.apiKeys.copyAddress(item.label)}
							doneLabel={t.apiKeys.copied}
							variant="secondary"
							className="size-9 min-h-0 min-w-0 gap-0 p-0 text-[0px] [&_svg]:size-5"
						/>,
						<span key="value" dir="ltr" className="block break-all text-start font-mono text-sm">
							{item.value}
						</span>,
					],
				}))}
			/>
		</SectionCard>
	);
}
