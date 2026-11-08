import { Modal, Notice, SkeletonRows, StatusChip } from "@nyxon/nasim";
import { Loadable } from "@/shared/Loadable";
import { t } from "@/strings";
import { usePlaybook } from "../api";

const P = t.reports.playbooks;

function Section({
	title,
	items,
	code,
}: {
	title: string;
	items: readonly string[];
	code?: boolean;
}) {
	return (
		<section className="flex flex-col gap-1.5">
			<h3 className="text-sm font-semibold">{title}</h3>
			<ul dir="ltr" className="flex flex-col gap-1.5 text-start text-sm">
				{items.map((item) => (
					<li
						key={item}
						className={code ? "rounded-lg bg-surface-secondary px-2 py-1 font-mono text-xs" : ""}
					>
						{item}
					</li>
				))}
			</ul>
		</section>
	);
}

// Causes, read-only checks, safe fixes and never-do rules for one issue code.
export function PlaybookModal({ code, onClose }: { code: string | null; onClose: () => void }) {
	const query = usePlaybook(code);
	return (
		<Modal
			isOpen={code !== null}
			onOpenChange={(open) => !open && onClose()}
			title={code ?? P.tableLabel}
			size="lg"
		>
			<Loadable query={query} skeleton={<SkeletonRows />}>
				{({ matched, playbook }) => (
					<div className="flex flex-col gap-4">
						<div className="flex flex-wrap items-center gap-2">
							<StatusChip
								tone={playbook.detector === "live" ? "success" : "neutral"}
								label={
									(P.detector as Record<string, string>)[playbook.detector] ?? playbook.detector
								}
								size="sm"
							/>
							<span dir="ltr" className="font-semibold">
								{playbook.title}
							</span>
						</div>
						<p className="text-sm">{playbook.summary_fa}</p>
						{matched ? null : <Notice tone="info">{P.generic}</Notice>}
						<p className="text-xs text-muted">{P.language}</p>
						<Section title={P.causes} items={playbook.causes} />
						<Section title={P.checks} items={playbook.checks} code />
						<Section title={P.fixes} items={playbook.fixes} />
						<Section title={P.never} items={playbook.never} />
						<Section title={P.source} items={playbook.source} />
					</div>
				)}
			</Loadable>
		</Modal>
	);
}
