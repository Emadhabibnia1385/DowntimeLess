import { CopyButton, Notice } from "@nyxon/nasim";
import type { ReactNode } from "react";
import type { GuideFa, GuideStep } from "@/api/generated/model";
import { formatNumber, t } from "@/strings";

const G = t.issueGuides;

// Shown to copy, never run: the panel has no execute path for these.
function Command({ cmd }: { cmd: string }) {
	return (
		<div className="flex items-start gap-2 rounded-xl border border-border bg-surface-secondary py-2 ps-3 pe-2">
			<span className="sr-only">{G.command}</span>
			<pre
				dir="ltr"
				className="min-w-0 flex-1 self-center whitespace-pre-wrap text-start font-mono text-xs leading-5 [overflow-wrap:anywhere]"
			>
				{cmd}
			</pre>
			<div className="flex shrink-0 flex-col items-end">
				<CopyButton value={cmd} label={G.copy} doneLabel={G.copied} />
			</div>
		</div>
	);
}

function Steps({ steps }: { steps: readonly GuideStep[] }) {
	return (
		<ol className="flex flex-col gap-3">
			{steps.map((step, index) => (
				<li key={`${index}-${step.text}`} className="flex gap-3">
					<span
						aria-hidden
						className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold tabular-nums text-accent-soft-foreground"
					>
						{formatNumber(index + 1)}
					</span>
					<div className="flex min-w-0 flex-1 flex-col gap-2">
						<p className="text-sm leading-6">{step.text}</p>
						{step.cmd ? <Command cmd={step.cmd} /> : null}
					</div>
				</li>
			))}
		</ol>
	);
}

function Bullets({ items }: { items: readonly string[] }) {
	return (
		<ul className="flex list-disc flex-col gap-1.5 ps-5 text-sm leading-6">
			{items.map((item) => (
				<li key={item}>{item}</li>
			))}
		</ul>
	);
}

function Part({ title, children }: { title: string; children: ReactNode }) {
	return (
		<section className="flex flex-col gap-2">
			<h3 className="font-semibold">{title}</h3>
			{children}
		</section>
	);
}

/** The guide for people: meaning, checks, fixes, the sign it is fixed, what never to do. */
export function GuideBody({ guide, generic }: { guide: GuideFa; generic: boolean }) {
	return (
		<div className="flex flex-col gap-5">
			{generic ? <Notice tone="info">{G.generic}</Notice> : null}
			<span dir="ltr" className="self-end font-mono text-xs text-muted">
				{guide.code}
			</span>
			<Part title={G.meaning}>
				<p className="text-sm leading-6">{guide.meaning}</p>
			</Part>
			<Part title={G.why}>
				<p className="text-sm leading-6">{guide.why}</p>
			</Part>
			<Part title={G.checks}>
				<p className="text-xs text-muted">{G.checksHint}</p>
				<Steps steps={guide.checks} />
			</Part>
			<Part title={G.fixes}>
				<Notice tone="warning">{G.fixesHint}</Notice>
				<Steps steps={guide.fixes} />
			</Part>
			<Part title={G.fixedWhen}>
				<Bullets items={guide.fixed_when} />
			</Part>
			<Part title={G.never}>
				<Bullets items={guide.never} />
			</Part>
		</div>
	);
}
