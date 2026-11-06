import { Button, Modal } from "@nyxon/nasim";
import { useState } from "react";
import type { ServerCreated } from "@/api/generated/model";
import { useServersCreate } from "@/api/generated/servers/servers";
import { useRefreshAll } from "@/shared/useRefreshAll";
import { t } from "@/strings";
import { InstallCommand } from "./InstallCommand";
import { ServerForm } from "./ServerForm";

// Two steps in one dialog: name the server, then show its one-time install command.
export function AddServerDialog({
	isOpen,
	onOpenChange,
}: {
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const [created, setCreated] = useState<ServerCreated | null>(null);
	const refresh = useRefreshAll();
	const create = useServersCreate({
		mutation: {
			onSuccess: (result) => {
				setCreated(result);
				void refresh();
			},
		},
	});
	const change = (open: boolean) => {
		onOpenChange(open);
		if (!open) {
			setCreated(null);
			create.reset();
		}
	};
	return (
		<Modal
			isOpen={isOpen}
			onOpenChange={change}
			title={created ? t.servers.installTitle : t.servers.addTitle}
			isDismissable={created !== null}
			footer={created ? <Button onPress={() => change(false)}>{t.common.done}</Button> : undefined}
		>
			{created ? (
				<InstallCommand serverId={created.server.id} command={created.install_command} />
			) : (
				<ServerForm
					defaults={{ name: "", alias: "", role: "relay" }}
					submitLabel={t.servers.create}
					error={create.error}
					onSubmit={(values) => create.mutate({ data: values })}
				/>
			)}
		</Modal>
	);
}
