import { Button, CopyButton, SectionCard, SelectField, SkeletonRows } from "@nyxon/nasim";
import { useState } from "react";
import { DownloadIcon } from "@/shared/icons";
import { Loadable } from "@/shared/Loadable";
import { formatNumber, t } from "@/strings";
import { useBriefing } from "../api";
import { DETAILS, type Detail } from "../lib/tabs";

const AI = t.reports.ai;
const detailOptions = DETAILS.map((value) => ({ value, label: AI.detail[value] }));

function download(text: string, detail: Detail) {
	const url = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" }));
	const link = document.createElement("a");
	link.href = url;
	link.download = `fleet-briefing-${detail}-${new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "")}.md`;
	link.click();
	URL.revokeObjectURL(url);
}

// The master's own Markdown for an assistant; its token count is about a quarter of its length.
export function BriefingTab() {
	const [detail, setDetail] = useState<Detail>("brief");
	const briefing = useBriefing(detail);
	const text = briefing.data;
	return (
		<SectionCard title={AI.cardTitle} description={AI.hint}>
			<div className="flex flex-col gap-4">
				<div className="flex flex-wrap items-end gap-3">
					<div className="w-44">
						<SelectField
							label={AI.detailLabel}
							value={detail}
							onChange={(next) => setDetail(next === "full" ? "full" : "brief")}
							options={detailOptions}
						/>
					</div>
					{text ? (
						<>
							<CopyButton value={text} label={AI.copy} variant="primary" size="md" />
							<Button variant="secondary" onPress={() => download(text, detail)}>
								<DownloadIcon aria-hidden />
								{AI.download}
							</Button>
							<span className="text-sm text-muted">
								{AI.size(formatNumber(Math.round(text.length / 4)))}
							</span>
						</>
					) : null}
				</div>
				<Loadable query={briefing} skeleton={<SkeletonRows />}>
					{(md) => (
						<section aria-label={AI.preLabel}>
							<pre
								dir="ltr"
								className="overflow-x-auto whitespace-pre-wrap break-words rounded-xl bg-surface-secondary p-3 text-start font-mono text-xs leading-5"
							>
								{md}
							</pre>
						</section>
					)}
				</Loadable>
			</div>
		</SectionCard>
	);
}
