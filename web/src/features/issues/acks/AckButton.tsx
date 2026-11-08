import { Button, Tooltip } from "@nyxon/nasim";
import { useState } from "react";
import { useCanCheck } from "@/features/auth/session";
import { CheckIcon } from "@/shared/icons";
import { t } from "@/strings";
import { AckDialog, type AckTarget } from "./AckDialog";

// Operators and up; the master enforces the same rank, this only hides what would be refused.
export function AckButton({ target }: { target: AckTarget }) {
	const allowed = useCanCheck();
	const [open, setOpen] = useState(false);
	if (!allowed) return null;
	const label = t.issueAcks.actionFor(target.title, target.server || t.common.none);
	return (
		<>
			<Tooltip>
				<Button
					isIconOnly
					size="sm"
					variant="secondary"
					aria-label={label}
					onPress={() => setOpen(true)}
				>
					<CheckIcon aria-hidden />
				</Button>
				<Tooltip.Content className="max-w-64 break-normal text-start">
					{t.issueAcks.action}
				</Tooltip.Content>
			</Tooltip>
			<AckDialog target={open ? target : null} onClose={() => setOpen(false)} />
		</>
	);
}
