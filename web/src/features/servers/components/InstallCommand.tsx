import { Button, CopyField, Notice, toast } from "@nyxon/nasim";
import { useState } from "react";
import { useServersNewEnrollToken } from "@/api/generated/servers/servers";
import { errorMessage } from "@/api/transport";
import { t } from "@/strings";

// The one-time install command with its explanation, and a button that issues a fresh token.
export function InstallCommand({
	serverId,
	command: initial,
}: {
	serverId: number;
	command: string | null;
}) {
	const [command, setCommand] = useState(initial);
	const issue = useServersNewEnrollToken({
		mutation: {
			onSuccess: (created) => {
				setCommand(created.install_command);
				toast.success(t.servers.newTokenDone);
			},
			onError: (error) => toast.danger(errorMessage(error)),
		},
	});
	return (
		<div className="flex flex-col gap-4">
			{command ? (
				<>
					<p className="text-sm">{t.servers.installBody}</p>
					<CopyField label={t.servers.installCommand} value={command} />
					<Notice tone="warning">{t.servers.installOnce}</Notice>
				</>
			) : null}
			<Button
				variant="secondary"
				isPending={issue.isPending}
				onPress={() => issue.mutate({ serverId })}
			>
				{command ? t.servers.newToken : t.servers.getCommand}
			</Button>
		</div>
	);
}
