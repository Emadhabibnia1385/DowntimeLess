import { Button, ConfirmDialog, EmptyState, SectionCard, StaticTable, toast } from "@nyxon/nasim";
import { useState } from "react";
import type { ChannelOut } from "@/api/generated/model";
import {
	useTelegramDeleteChannel,
	useTelegramTestChannel,
} from "@/api/generated/telegram/telegram";
import { errorMessage } from "@/api/transport";
import { AddIcon, TrashIcon } from "@/shared/icons";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";
import { AddChannelDialog } from "./AddChannelDialog";

// The Telegram channels alerts can be routed to: add by hand, send a test message, delete.
export function ChannelsCard({ channels }: { channels: readonly ChannelOut[] }) {
	const refresh = useRefreshAll();
	const [adding, setAdding] = useState(false);
	const [deleting, setDeleting] = useState<ChannelOut | null>(null);
	const test = useTelegramTestChannel({
		mutation: {
			onSuccess: () => toast.success(t.channels.tested),
			onError: (error) => toast.danger(errorMessage(error)),
		},
	});
	const remove = useTelegramDeleteChannel({
		mutation: {
			onSuccess: () => {
				setDeleting(null);
				void refresh();
			},
			onError: (error) => {
				setDeleting(null);
				toast.danger(errorMessage(error));
			},
		},
	});
	return (
		<>
			<SectionCard
				title={t.channels.title}
				description={t.channels.hint}
				actions={
					<Button variant="secondary" onPress={() => setAdding(true)}>
						<AddIcon aria-hidden />
						{t.channels.add}
					</Button>
				}
			>
				{channels.length ? (
					<StaticTable
						caption={t.channels.tableLabel}
						className="min-w-[32rem]"
						columns={[
							t.channels.colName,
							t.channels.colChat,
							t.channels.colTest,
							t.channels.colDelete,
						]}
						rows={channels.map((channel) => ({
							id: String(channel.id),
							cells: [
								<span key="name" className="font-semibold">
									{channel.name}
								</span>,
								<span key="chat" dir="ltr" className="inline-block font-mono text-sm">
									{channel.chat_id}
								</span>,
								<Button
									key="test"
									size="sm"
									variant="secondary"
									aria-label={t.channels.testOf(channel.name)}
									isPending={test.isPending && test.variables?.channelId === channel.id}
									onPress={() => test.mutate({ channelId: channel.id })}
								>
									{t.channels.test}
								</Button>,
								<Button
									key="delete"
									isIconOnly
									size="sm"
									variant="danger-soft"
									aria-label={t.channels.deleteOf(channel.name)}
									onPress={() => setDeleting(channel)}
								>
									<TrashIcon aria-hidden />
								</Button>,
							],
						}))}
					/>
				) : (
					<EmptyState title={t.channels.emptyTitle} description={t.channels.empty} />
				)}
			</SectionCard>
			<AddChannelDialog isOpen={adding} onOpenChange={setAdding} />
			<ConfirmDialog
				isOpen={deleting !== null}
				onOpenChange={(open) => !open && setDeleting(null)}
				tone="danger"
				title={t.channels.deleteTitle}
				description={t.channels.deleteBody}
				confirmLabel={t.common.delete}
				isPending={remove.isPending}
				onConfirm={() => {
					if (deleting) remove.mutate({ channelId: deleting.id });
				}}
			/>
		</>
	);
}
