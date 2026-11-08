import { Button, toast } from "@nyxon/nasim";
import { useChecksSetIgnore } from "@/api/generated/checks/checks";
import type { IgnoreSetKind } from "@/api/generated/model";
import { errorMessage } from "@/api/transport";
import { useRefreshAll } from "@/shared/useRefreshAll";

// Marks a retired node or container, or a group-less inbound, as deliberate (or undoes it).
export function IgnoreButton({
	serverId,
	kind,
	name,
	ignored,
	label,
	ariaLabel,
}: {
	serverId: number;
	kind: IgnoreSetKind;
	name: string;
	ignored: boolean;
	label: string;
	ariaLabel: string;
}) {
	const refresh = useRefreshAll();
	const save = useChecksSetIgnore();
	const press = async () => {
		try {
			await save.mutateAsync({ serverId, data: { kind, name, ignored: !ignored } });
			void refresh();
		} catch (error) {
			toast.danger(errorMessage(error));
		}
	};
	return (
		<Button
			size="sm"
			variant="secondary"
			aria-label={ariaLabel}
			isPending={save.isPending}
			onPress={() => void press()}
		>
			{label}
		</Button>
	);
}
