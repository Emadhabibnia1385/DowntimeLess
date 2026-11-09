import {
	Button,
	CheckboxField,
	CopyField,
	LinkButton,
	Notice,
	Spinner,
	StatusChip,
	TextField,
	toast,
} from "@nyxon/nasim";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
	useAuthLinkCancel,
	useAuthLinkConfirm,
	useAuthLinkStart,
	useAuthLinkView,
} from "@/api/generated/auth/auth";
import type { LinkStart, LinkView, MergePlan, UserOut } from "@/api/generated/model";
import { errorMessage } from "@/api/transport";
import { asRole, useStartSession } from "@/features/auth";
import { TelegramIcon } from "@/shared/icons";
import { formatDateTime, formatNumber, t } from "@/strings";

const L = t.account.link;
const M = t.account.merge;
const WAITING = new Set(["pending", "seen"]);
const roleName = (role: string | null | undefined) =>
	role ? t.members.roles[asRole(role)] : M.none;
const who = (view: LinkView) =>
	view.telegram
		? L.telegramWho(view.telegram.name || String(view.telegram.id), view.telegram.username ?? "")
		: "";

function CodeField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
	return (
		<TextField
			label={L.code}
			description={L.codeHint}
			value={value}
			onChange={(v) => onChange(v.replace(/\D/g, "").slice(0, 6))}
			inputMode="numeric"
			autoComplete="one-time-code"
			dir="ltr"
			maxLength={6}
		/>
	);
}

function Merge({
	plan,
	busy,
	canSubmit,
	code,
	onCode,
	onConfirm,
}: {
	plan: MergePlan;
	busy: boolean;
	canSubmit: boolean;
	code: string;
	onCode: (v: string) => void;
	onConfirm: () => void;
}) {
	const [sure, setSure] = useState(false);
	const other = plan.other;
	return (
		<div className="flex flex-col gap-3">
			<Notice tone="warning">
				<span className="font-semibold">{M.title}</span>
			</Notice>
			<p className="text-sm leading-7">{M.lead}</p>
			<ul className="flex list-disc flex-col gap-1.5 ps-5 text-sm leading-7">
				<li>{M.survivorThis}</li>
				<li>
					{M.other}: {other.name || t.members.noName} ·{" "}
					{other.username ? M.otherUsername(other.username) : M.noUsername}
				</li>
				{plan.api_keys > 0 ? <li>{M.keys(formatNumber(plan.api_keys))}</li> : null}
				{plan.moves_password ? <li>{M.password}</li> : null}
				<li>{M.sessions}</li>
			</ul>
			<h4 className="font-semibold">{M.workspacesTitle}</h4>
			{plan.workspaces.length === 0 ? (
				<p className="text-sm text-muted">{M.noWorkspaces}</p>
			) : (
				<ul
					aria-label={M.workspacesTitle}
					className="flex flex-col divide-y divide-border rounded-2xl border border-border"
				>
					{plan.workspaces.map((w) => (
						<li key={w.workspace_id} className="flex flex-col gap-1.5 p-3">
							<span className="flex flex-wrap items-center gap-2">
								<span className="font-semibold">{w.name}</span>
								{w.owned ? <StatusChip tone="warning" size="sm" label={M.owned} /> : null}
							</span>
							<span className="text-sm text-muted">
								{M.colTheirRole}: {roleName(w.role)} · {M.colYourRole}: {roleName(w.survivor_role)}
							</span>
							<span className="flex items-center gap-2 text-sm">
								{M.colResult}:
								<StatusChip tone="info" size="sm" label={roleName(w.result_role)} />
							</span>
						</li>
					))}
				</ul>
			)}
			<CodeField value={code} onChange={onCode} />
			<CheckboxField value={sure} onChange={setSure}>
				{M.understand}
			</CheckboxField>
			<Button
				variant="danger-soft"
				isDisabled={!sure || !canSubmit}
				isPending={busy}
				onPress={onConfirm}
			>
				{M.submit}
			</Button>
		</div>
	);
}

function Flow({ started, onEnd }: { started: LinkStart; onEnd: () => void }) {
	const queryClient = useQueryClient();
	const startSession = useStartSession();
	const view = useAuthLinkView(started.link_id, {
		query: {
			refetchInterval: (q) => (WAITING.has(q.state.data?.status ?? "pending") ? 2000 : false),
		},
	});
	const cancel = useAuthLinkCancel({ mutation: { onSettled: onEnd } });
	const confirm = useAuthLinkConfirm({
		mutation: {
			onSuccess: (done) => {
				startSession(done.user);
				toast.success(done.merged ? L.merged : L.done, {
					description: done.claimed_workspaces
						? L.claimed(formatNumber(done.claimed_workspaces))
						: undefined,
				});
				void queryClient.invalidateQueries();
				onEnd();
			},
		},
	});
	const [code, setCode] = useState("");
	const data = view.data;
	const status = data?.status ?? "pending";
	const hasCode = code.length === 6;
	const ask = (merge: MergePlan | null | undefined) =>
		confirm.mutate({
			linkId: started.link_id,
			data: merge ? { code, merge: true, fingerprint: merge.fingerprint } : { code },
		});
	if (status === "denied" || status === "expired" || status === "done") {
		return (
			<div className="flex flex-col items-start gap-3">
				<Notice tone="warning">{status === "expired" ? L.expired : L.denied}</Notice>
				<Button variant="secondary" onPress={onEnd}>
					{L.again}
				</Button>
			</div>
		);
	}
	return (
		<div className="flex flex-col gap-4">
			{status === "confirmed" && data ? (
				<div className="flex flex-col gap-3">
					<h3 className="font-semibold">{L.step2}</h3>
					<Notice tone="warning">{L.notYouWarning}</Notice>
					<p className="text-sm font-semibold" dir="auto">
						{who(data)}
					</p>
					{data.merge ? (
						<Merge
							plan={data.merge}
							busy={confirm.isPending}
							canSubmit={hasCode}
							code={code}
							onCode={setCode}
							onConfirm={() => ask(data.merge)}
						/>
					) : (
						<>
							<p className="text-sm leading-7">{L.plainBody(who(data))}</p>
							<CodeField value={code} onChange={setCode} />
							<Button isDisabled={!hasCode} isPending={confirm.isPending} onPress={() => ask(null)}>
								{L.confirm}
							</Button>
						</>
					)}
				</div>
			) : (
				<div className="flex flex-col gap-3">
					<p className="text-sm leading-7">{L.step1}</p>
					<LinkButton href={started.deep_link} target="_blank" fullWidth>
						<TelegramIcon aria-hidden />
						{L.openInTelegram}
					</LinkButton>
					<div className="min-w-0">
						<CopyField label={L.linkLabel} value={started.deep_link} />
					</div>
					<output className="flex items-center gap-2 text-sm text-muted">
						<Spinner size="sm" />
						{status === "seen" && data ? L.seen(who(data)) : L.waiting}
					</output>
					{data ? (
						<p className="text-xs text-muted">{L.expiresAt(formatDateTime(data.expires_at))}</p>
					) : null}
				</div>
			)}
			{confirm.error ? (
				<Notice tone="danger" role="alert">
					{errorMessage(confirm.error)}
				</Notice>
			) : null}
			<Button
				variant="ghost"
				isPending={cancel.isPending}
				onPress={() => cancel.mutate({ linkId: started.link_id })}
			>
				{L.cancel}
			</Button>
		</div>
	);
}

// Not linked yet: a bot link, a yes in Telegram, then the final yes here (merge plan if needed).
export function TelegramLink({ user }: { user: UserOut }) {
	const [started, setStarted] = useState<LinkStart | null>(null);
	const start = useAuthLinkStart({ mutation: { onSuccess: setStarted } });
	if (user.tg_linked) return null;
	if (started) return <Flow started={started} onEnd={() => setStarted(null)} />;
	return (
		<div className="flex flex-col items-start gap-3">
			<p className="text-sm leading-7 text-muted">{L.startHint}</p>
			{start.error ? (
				<Notice tone="danger" role="alert">
					{errorMessage(start.error)}
				</Notice>
			) : null}
			<Button isPending={start.isPending} onPress={() => start.mutate()}>
				<TelegramIcon aria-hidden />
				{start.isPending ? L.opening : L.start}
			</Button>
		</div>
	);
}
